"""
algorand_service.py — Algorand blockchain interactions
======================================================
Handles on-chain registration, KYC status checks, and revocation.
Uses algosdk directly for testnet interactions.
"""
import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod

logger = logging.getLogger(__name__)

ALGOD_SERVER = "https://testnet-api.algonode.cloud"


def _sel(sig: str) -> bytes:
    """Compute ABI method selector (SHA512/256 first 4 bytes)."""
    return hashlib.new("sha512_256", sig.encode()).digest()[:4]


def _get_client(algod_server: str = ALGOD_SERVER, algod_token: str = "") -> algod.AlgodClient:
    return algod.AlgodClient(algod_token, algod_server)


def _get_account(deployer_mnemonic: str) -> tuple[str, bytes]:
    """Returns (address, private_key) from mnemonic."""
    pk = mnemonic.to_private_key(deployer_mnemonic)
    addr = account.address_from_private_key(pk)
    return addr, pk


def _wait(client: algod.AlgodClient, txid: str, rounds: int = 12) -> dict:
    last = client.status()["last-round"]
    for _ in range(rounds):
        info = client.pending_transaction_info(txid)
        if info.get("confirmed-round", 0) > 0:
            return info
        client.status_after_block(last + 1)
        last += 1
    raise TimeoutError(f"Transaction not confirmed: {txid}")


def register_nullifier(
    deployer_mnemonic: str,
    nullifier_hex: str,
    wallet_address: str,
    nr_app_id: int,
    algod_server: str = ALGOD_SERVER,
    algod_token: str = "",
) -> str:
    """
    Register a verified nullifier on the NullifierRegistry contract.
    Sends an atomic group: fund box MBR + call register().

    Returns: confirmed transaction ID
    """
    client = _get_client(algod_server, algod_token)
    sender, pk = _get_account(deployer_mnemonic)
    app_addr = transaction.logic.get_application_address(nr_app_id)

    # Build box name: "nul_" + 32 bytes nullifier
    nullifier_bytes = bytes.fromhex(nullifier_hex.zfill(64))
    box_name = b"nul_" + nullifier_bytes

    # ABI encode nullifier as byte[] (2-byte length + bytes)
    enc_nullifier = len(nullifier_bytes).to_bytes(2, "big") + nullifier_bytes

    # ABI encode wallet as 32-byte public key
    # Algorand address = base32(pubkey_32bytes + checksum_4bytes)
    # We need to pad to a multiple of 8 for base32, decode, then take first 32 bytes
    addr_padded = wallet_address + '=' * (-len(wallet_address) % 8)
    wallet_decoded = base64.b32decode(addr_padded)   # 36 bytes: 32 pubkey + 4 checksum
    wallet_pk = wallet_decoded[:32]                   # first 32 bytes = raw public key

    sp = client.suggested_params()

    # Txn 1: Fund NullifierRegistry for box MBR (0.05 ALGO)
    fund_txn = transaction.PaymentTxn(
        sender=sender, sp=sp, receiver=app_addr, amt=50_000
    )

    # Txn 2: Call register(byte[], address)void
    register_sel = _sel("register(byte[],address)void")
    reg_txn = transaction.ApplicationNoOpTxn(
        sender=sender, sp=sp, index=nr_app_id,
        app_args=[register_sel, enc_nullifier, wallet_pk],
        accounts=[wallet_address],
        boxes=[(nr_app_id, box_name)],
    )

    # Atomic group
    transaction.assign_group_id([fund_txn, reg_txn])
    signed = [fund_txn.sign(pk), reg_txn.sign(pk)]

    txid = client.send_transactions(signed)
    _wait(client, txid)
    logger.info(f"Nullifier registered on-chain: {txid}")
    return txid


def get_kyc_status(
    nr_app_id: int,
    algod_server: str = ALGOD_SERVER,
    algod_token: str = "",
) -> dict[str, Any]:
    """Read global state from NullifierRegistry."""
    client = _get_client(algod_server, algod_token)
    try:
        info = client.application_info(nr_app_id)
        state = {}
        for kv in info.get("params", {}).get("global-state", []):
            key = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
            val = kv["value"]
            state[key] = val["uint"] if val["type"] == 2 else base64.b64decode(val["bytes"])
        return {
            "app_id": nr_app_id,
            "total_registered": state.get("total_registered", 0),
        }
    except Exception as e:
        logger.error(f"Failed to read KYC status: {e}")
        return {"app_id": nr_app_id, "total_registered": 0, "error": str(e)}


def is_nullifier_registered(
    nullifier_hex: str,
    nr_app_id: int,
    algod_server: str = ALGOD_SERVER,
    algod_token: str = "",
) -> bool:
    """Check if a nullifier box exists in NullifierRegistry."""
    client = _get_client(algod_server, algod_token)
    nullifier_bytes = bytes.fromhex(nullifier_hex.zfill(64))
    box_name = b"nul_" + nullifier_bytes
    try:
        box = client.application_box_by_name(nr_app_id, box_name)
        return len(box.get("value", "")) > 0
    except Exception:
        return False


def invalidate_nullifier(
    deployer_mnemonic: str,
    nullifier_hex: str,
    nr_app_id: int,
    algod_server: str = ALGOD_SERVER,
    algod_token: str = "",
) -> str:
    """
    Revoke a credential by invalidating its nullifier on NullifierRegistry.
    Only the issuer (deployer) can call this.
    """
    client = _get_client(algod_server, algod_token)
    sender, pk = _get_account(deployer_mnemonic)

    nullifier_bytes = bytes.fromhex(nullifier_hex.zfill(64))
    box_name = b"nul_" + nullifier_bytes
    enc_nullifier = len(nullifier_bytes).to_bytes(2, "big") + nullifier_bytes

    sp = client.suggested_params()
    invalidate_sel = _sel("invalidate(byte[])void")
    txn = transaction.ApplicationNoOpTxn(
        sender=sender, sp=sp, index=nr_app_id,
        app_args=[invalidate_sel, enc_nullifier],
        boxes=[(nr_app_id, box_name)],
    )
    txid = client.send_transaction(txn.sign(pk))
    _wait(client, txid)
    logger.info(f"Nullifier invalidated on-chain: {txid}")
    return txid

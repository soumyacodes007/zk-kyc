#!/usr/bin/env python3
"""
deploy_testnet_direct.py — Deploy all AlgoKYC contracts to Algorand Testnet
===========================================================================
Uses algosdk directly to create fresh apps — no algokit deploy() update-detection.
Run: python deploy_testnet_direct.py

Prereqs:
  .env must have: ALGOD_SERVER, ALGOD_PORT, ALGOD_TOKEN, DEPLOYER_MNEMONIC
  Deployer account must have ≥ 10 ALGO (for 4 contracts + MBR funding)
"""
import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s: %(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS = Path(__file__).parent / "smart_contracts" / "artifacts"
DEPLOYED_JSON = Path(__file__).parent / "deployed_contracts.json"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_algod_client():
    server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    port   = os.environ.get("ALGOD_PORT", "443")
    token  = os.environ.get("ALGOD_TOKEN", "")
    url    = f"{server}:{port}" if not server.endswith(str(port)) else server
    return algod.AlgodClient(token, url, headers={"X-API-Key": token} if token else {})

def get_deployer_key():
    mn = os.environ["DEPLOYER_MNEMONIC"]
    return mnemonic.to_private_key(mn)

def compile_teal(client: algod.AlgodClient, teal: str) -> bytes:
    result = client.compile(teal)
    return base64.b64decode(result["result"])

def wait_confirmed(client, txid, timeout=10):
    last_round = client.status()["last-round"]
    for _ in range(timeout):
        pending = client.pending_transaction_info(txid)
        if pending.get("confirmed-round", 0) > 0:
            return pending
        client.status_after_block(last_round + 1)
        last_round += 1
    raise TimeoutError(f"Transaction {txid} not confirmed after {timeout} rounds")

def create_app(client, private_key, approval_teal, clear_teal,
               global_ints=0, global_bytes=0,
               local_ints=0, local_bytes=0,
               fund_algo=1) -> dict:
    """Create a new application, fund it, return app info."""
    sender = account.address_from_private_key(private_key)

    approval_prog = compile_teal(client, approval_teal)
    clear_prog    = compile_teal(client, clear_teal)

    sp = client.suggested_params()
    txn = transaction.ApplicationCreateTxn(
        sender=sender,
        sp=sp,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_prog,
        clear_program=clear_prog,
        global_schema=transaction.StateSchema(global_ints, global_bytes),
        local_schema=transaction.StateSchema(local_ints, local_bytes),
        # ABI create method call: method selector + args
        # Since create() has no args, just the 4-byte selector
        app_args=[b'\x4c\x5c\x61\xba'],  # keccak256("create()void")[:4]
    )
    signed = txn.sign(private_key)
    txid   = client.send_transaction(signed)
    logger.info(f"    Create txn: {txid}")
    result = wait_confirmed(client, txid)
    app_id = result["application-index"]

    app_addr = transaction.logic.get_application_address(app_id)
    logger.info(f"    App ID: {app_id}, Address: {app_addr}")

    # Fund the app account for MBR
    pay_txn = transaction.PaymentTxn(
        sender=sender,
        sp=sp,
        receiver=app_addr,
        amt=int(fund_algo * 1_000_000),
    )
    signed_pay = pay_txn.sign(private_key)
    pay_txid   = client.send_transaction(signed_pay)
    wait_confirmed(client, pay_txid)
    logger.info(f"    Funded with {fund_algo} ALGO")

    return {"app_id": app_id, "app_address": app_addr}


def read_teal(contract_name: str, kind: str = "approval") -> str:
    """Read a TEAL file from artifacts dir."""
    arts = ARTIFACTS / contract_name
    # Find the .teal file
    matches = list(arts.glob(f"*.{kind}.teal"))
    if not matches:
        raise FileNotFoundError(f"No {kind}.teal in {arts}")
    return matches[0].read_text(encoding="utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────

def deploy_all():
    logger.info("=== AlgoKYC Testnet Deploy (Direct) ===")

    client = get_algod_client()
    pk     = get_deployer_key()
    sender = account.address_from_private_key(pk)

    logger.info(f"Network : {os.environ.get('ALGOD_SERVER')}")
    logger.info(f"Deployer: {sender}")

    info = client.account_info(sender)
    balance_algo = info["amount"] / 1_000_000
    logger.info(f"Balance : {balance_algo:.4f} ALGO")
    if balance_algo < 2:
        raise ValueError(
            f"Need ≥2 ALGO, have {balance_algo:.4f}. "
            f"Fund at https://bank.testnet.algorand.network/?account={sender}"
        )

    deployed = {"network": os.environ.get("ALGOD_SERVER"), "deployer": sender}

    contracts = [
        # (artifact_dir, contract label, global_ints, global_bytes, local_ints, local_bytes, fund)
        ("nullifier_registry",  "NullifierRegistry",  1, 1, 0, 0, 0.5),
        ("smt_registry",        "SMTRegistry",         2, 2, 0, 0, 0.5),
        ("kyc_box_storage",     "KYCBoxStorage",       1, 1, 0, 0, 0.5),
        ("credential_manager",  "CredentialManager",   3, 1, 0, 0, 0.5),
    ]

    for i, (art_dir, label, gi, gb, li, lb, fund) in enumerate(contracts, 1):
        logger.info(f"\n[{i}/{len(contracts)}] Deploying {label}...")
        approval = read_teal(art_dir, "approval")
        clear    = read_teal(art_dir, "clear")

        info_app = create_app(
            client, pk,
            approval, clear,
            global_ints=gi, global_bytes=gb,
            local_ints=li,  local_bytes=lb,
            fund_algo=fund,
        )
        deployed[art_dir] = info_app
        logger.info(f"  ✅ {label}: app_id={info_app['app_id']}")
        logger.info(f"     https://testnet.algoexplorer.io/application/{info_app['app_id']}")

    # Save
    DEPLOYED_JSON.write_text(json.dumps(deployed, indent=2))
    logger.info(f"\n✅ All {len(contracts)} contracts deployed!")

    print("\n" + "="*65)
    print("ALGOKYC TESTNET — DEPLOYED CONTRACT IDs")
    print("="*65)
    for key, val in deployed.items():
        if isinstance(val, dict) and "app_id" in val:
            print(f"  {key:25s} {val['app_id']}")
    print("="*65)
    print(f"\nSaved to: {DEPLOYED_JSON}")
    print("Next: python run_e2e_tests.py")

    return deployed


if __name__ == "__main__":
    deploy_all()

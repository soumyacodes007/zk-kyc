#!/usr/bin/env python3
"""
deploy_credential_manager.py — Deploy CredentialManager to Algorand Testnet
===========================================================================
CredentialManager is special:
  - create() creates an inner ASA → app must have 0.1 ALGO MBR before create runs
  - Solution: rewrite create() to be simple init, add initialize_asa() called after funding

Run: python deploy_credential_manager.py
"""
import base64
import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s: %(message)s")
logger = logging.getLogger(__name__)

DEPLOYED_JSON   = Path(__file__).parent / "deployed_contracts.json"
CONTRACT_SRC    = Path(__file__).parent / "smart_contracts/credential_manager/contract.py"
ART_DIR         = Path(__file__).parent / "smart_contracts/credential_manager/smart_contracts/artifacts/credential_manager"


def sel(sig: str) -> bytes:
    """ABI method selector = first 4 bytes of SHA512/256(sig)."""
    return hashlib.new("sha512_256", sig.encode()).digest()[:4]


def get_algod_client():
    server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    token  = os.environ.get("ALGOD_TOKEN", "")
    return algod.AlgodClient(token, server)


def get_deployer_key():
    return mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])


def compile_teal(client, teal: str) -> bytes:
    return base64.b64decode(client.compile(teal)["result"])


def wait_confirmed(client, txid, timeout=12):
    last_round = client.status()["last-round"]
    for _ in range(timeout):
        info = client.pending_transaction_info(txid)
        if info.get("confirmed-round", 0) > 0:
            return info
        client.status_after_block(last_round + 1)
        last_round += 1
    raise TimeoutError(f"Not confirmed: {txid}")


def rewrite_and_compile_contract():
    """Rewrite contract to split create + initialize_asa, then recompile."""
    NEW_CONTRACT = '''\
"""
CredentialManager — AlgoKYC v1
Issues and manages non-transferable KYC credential ASAs.

Deployment flow:
  1. deploy_create()         → bare create, sets issuer
  2. fund app with 0.3 ALGO  → for ASA creation MBR
  3. initialize_asa()        → creates the KYCRED ASA, returns ASA ID
"""
from algopy import ARC4Contract, Account, Asset, Bytes, Global, Txn, UInt64, arc4, itxn


class CredentialManager(ARC4Contract):
    """Issues and revokes non-transferable KYC credential ASAs."""

    def __init__(self) -> None:
        self.issuer = Account()
        self.credential_asa_id = UInt64(0)
        self.total_issued = UInt64(0)
        self.total_revoked = UInt64(0)

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Initialize — deployer becomes issuer. Fund app with 0.3 ALGO then call initialize_asa()."""
        self.issuer = Txn.sender
        self.total_issued = UInt64(0)
        self.total_revoked = UInt64(0)

    @arc4.abimethod()
    def initialize_asa(self) -> UInt64:
        """
        Create the KYC credential ASA. Must be called AFTER funding app with >= 0.3 ALGO.
        Returns the new ASA ID. App address is manager/clawback/freeze.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        assert self.credential_asa_id == UInt64(0), "ASA already created"

        result = itxn.AssetConfig(
            total=1_000_000_000,
            decimals=0,
            default_frozen=True,
            unit_name=b"KYCRED",
            asset_name=b"AlgoKYC Credential",
            url=b"https://algokyc.dev",
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            freeze=Global.current_application_address,
            reserve=Global.current_application_address,
            fee=0,
        ).submit()

        self.credential_asa_id = result.created_asset.id
        return result.created_asset.id

    @arc4.abimethod()
    def issue_credential(self, recipient: Account, nullifier: Bytes) -> None:
        """Issue a KYC credential to a verified wallet. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"

        asa = Asset(self.credential_asa_id)

        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=False,
            fee=0,
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=asa,
            asset_receiver=recipient,
            asset_amount=1,
            note=nullifier,
            fee=0,
        ).submit()

        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=True,
            fee=0,
        ).submit()

        self.total_issued += UInt64(1)

    @arc4.abimethod()
    def revoke_credential(self, wallet: Account, nullifier: Bytes) -> None:
        """Revoke credential via clawback. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"

        itxn.AssetTransfer(
            xfer_asset=Asset(self.credential_asa_id),
            asset_sender=wallet,
            asset_receiver=Global.current_application_address,
            asset_amount=1,
            note=nullifier,
            fee=0,
        ).submit()

        self.total_revoked += UInt64(1)

    @arc4.abimethod(readonly=True)
    def get_credential_asa_id(self) -> UInt64:
        """Return the credential ASA ID."""
        return self.credential_asa_id

    @arc4.abimethod(readonly=True)
    def get_total_issued(self) -> UInt64:
        return self.total_issued

    @arc4.abimethod(readonly=True)
    def get_total_revoked(self) -> UInt64:
        return self.total_revoked

    @arc4.abimethod()
    def update_issuer(self, new_issuer: Account) -> None:
        """Transfer issuer role. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"
        self.issuer = new_issuer
'''

    CONTRACT_SRC.write_text(NEW_CONTRACT, encoding="utf-8")
    logger.info("Wrote updated CredentialManager contract")

    ART_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["algokit", "compile", "python", str(CONTRACT_SRC), f"--out-dir={ART_DIR}"],
        capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Compile failed:\n{result.stdout}\n{result.stderr}")
    logger.info("CredentialManager compiled OK")


def deploy():
    logger.info("=== Deploying CredentialManager ===")

    # Rewrite and compile
    rewrite_and_compile_contract()

    client = get_algod_client()
    pk     = get_deployer_key()
    sender = account.address_from_private_key(pk)

    info_acc = client.account_info(sender)
    logger.info(f"Deployer: {sender} | Balance: {info_acc['amount']/1e6:.4f} ALGO")

    # Load compiled TEAL
    approval_teal = next(ART_DIR.glob("*.approval.teal")).read_text(encoding="utf-8")
    clear_teal    = next(ART_DIR.glob("*.clear.teal")).read_text(encoding="utf-8")
    approval_prog = compile_teal(client, approval_teal)
    clear_prog    = compile_teal(client, clear_teal)

    create_selector = sel("create()void")
    init_selector   = sel("initialize_asa()uint64")
    logger.info(f"create()void selector       : {create_selector.hex()}")
    logger.info(f"initialize_asa()uint64 sel  : {init_selector.hex()}")

    sp = client.suggested_params()

    # ── Step 1: Create the app ────────────────────────────────────────────────
    create_txn = transaction.ApplicationCreateTxn(
        sender=sender, sp=sp,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_prog,
        clear_program=clear_prog,
        global_schema=transaction.StateSchema(num_uints=3, num_byte_slices=1),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        app_args=[create_selector],
    )
    signed = create_txn.sign(pk)
    txid = client.send_transaction(signed)
    logger.info(f"Step 1 — create txn: {txid}")
    res = wait_confirmed(client, txid)
    app_id   = res["application-index"]
    app_addr = transaction.logic.get_application_address(app_id)
    logger.info(f"   App ID: {app_id}, Address: {app_addr}")

    # ── Step 2: Fund app with 0.3 ALGO (ASA MBR + buffer) ────────────────────
    sp = client.suggested_params()
    fund_txn = transaction.PaymentTxn(
        sender=sender, sp=sp, receiver=app_addr, amt=300_000
    )
    fund_txid = client.send_transaction(fund_txn.sign(pk))
    wait_confirmed(client, fund_txid)
    logger.info(f"Step 2 — funded 0.3 ALGO to app: {fund_txid}")

    # ── Step 3: Call initialize_asa() — creates the KYCRED ASA ───────────────
    sp = client.suggested_params()
    sp.fee     = 2000  # outer txn covers inner AssetConfig (inner fee=0)
    sp.flat_fee = True
    init_txn = transaction.ApplicationNoOpTxn(
        sender=sender, sp=sp, index=app_id,
        app_args=[init_selector],
    )
    init_txid = client.send_transaction(init_txn.sign(pk))
    logger.info(f"Step 3 — initialize_asa txn: {init_txid}")
    init_res = wait_confirmed(client, init_txid)

    # Extract ASA ID from ABI return value in logs
    asa_id = None
    raw_logs = init_res.get("logs", [])
    if raw_logs:
        raw = base64.b64decode(raw_logs[0])
        # ABI return prefix = 0x151f7c75, then 8-byte big-endian uint64
        if len(raw) >= 12 and raw[:4] == bytes.fromhex("151f7c75"):
            asa_id = int.from_bytes(raw[4:12], "big")
    logger.info(f"   Credential ASA ID: {asa_id}")

    # ── Save to deployed_contracts.json ──────────────────────────────────────
    deployed = {}
    if DEPLOYED_JSON.exists():
        deployed = json.loads(DEPLOYED_JSON.read_text())

    deployed["credential_manager"] = {
        "app_id":            app_id,
        "app_address":       app_addr,
        "credential_asa_id": asa_id,
        "explorer":          f"https://testnet.algoexplorer.io/application/{app_id}",
    }
    DEPLOYED_JSON.write_text(json.dumps(deployed, indent=2))

    print("\n" + "="*65)
    print("✅ CREDENTIAL MANAGER DEPLOYED!")
    print(f"   app_id            : {app_id}")
    print(f"   app_address       : {app_addr}")
    print(f"   credential_asa_id : {asa_id}")
    print(f"   explorer          : https://testnet.algoexplorer.io/application/{app_id}")
    print("="*65)
    return app_id


if __name__ == "__main__":
    deploy()

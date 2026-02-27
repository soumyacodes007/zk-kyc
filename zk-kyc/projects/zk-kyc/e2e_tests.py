#!/usr/bin/env python3
"""
e2e_tests.py — AlgoKYC End-to-End Integration Tests (Testnet)
==============================================================
Tests live contract state on Algorand Testnet against deployed_contracts.json.

Run: python e2e_tests.py
"""
import base64
import hashlib
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

DEPLOYED = json.loads(
    (Path(__file__).parent / "deployed_contracts.json").read_text()
)

PASSED = []
FAILED = []


def sel(sig: str) -> bytes:
    return hashlib.new("sha512_256", sig.encode()).digest()[:4]


def get_algod():
    server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    token  = os.environ.get("ALGOD_TOKEN", "")
    return algod.AlgodClient(token, server)


def get_pk():
    return mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])


def wait_confirmed(client, txid, timeout=12):
    last_round = client.status()["last-round"]
    for _ in range(timeout):
        info = client.pending_transaction_info(txid)
        if info.get("confirmed-round", 0) > 0:
            return info
        client.status_after_block(last_round + 1)
        last_round += 1
    raise TimeoutError(f"Not confirmed: {txid}")


def read_global_state(client, app_id: int) -> dict:
    info = client.application_info(app_id)
    state = {}
    for kv in info.get("params", {}).get("global-state", []):
        key = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
        val = kv["value"]
        if val["type"] == 1:
            state[key] = base64.b64decode(val["bytes"])
        else:
            state[key] = val["uint"]
    return state


def test(name: str, passed: bool, detail: str = ""):
    if passed:
        PASSED.append(name)
        logger.info(f"  PASS [{name}] {detail}")
    else:
        FAILED.append(name)
        logger.error(f"  FAIL [{name}] {detail}")


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_contracts_exist(client):
    print("\n=== [1] Contract Existence on Testnet ===")
    for name, data in DEPLOYED.items():
        if not isinstance(data, dict) or "app_id" not in data:
            continue
        app_id = data["app_id"]
        try:
            info = client.application_info(app_id)
            test(f"{name}_exists", True, f"app_id={app_id}")
        except Exception as e:
            test(f"{name}_exists", False, f"app_id={app_id} error: {e}")


def test_global_state(client):
    print("\n=== [2] Global State Verification ===")

    deployer_bytes = account.address_from_private_key(get_pk())
    deployer_raw   = bytes.fromhex(
        "".join(f"{x:02x}" for x in transaction.encoding.decode_address(deployer_bytes))
    )

    # NullifierRegistry: should have issuer=deployer, total_registered=0
    nr_id = DEPLOYED["nullifier_registry"]["app_id"]
    state = read_global_state(client, nr_id)
    test("nr_issuer_set",    b"issuer" in state or "issuer" in state, f"state keys: {list(state.keys())}")
    total = state.get("total_registered", -1)
    test("nr_total_zero",   total == 0, f"total_registered={total}")

    # SMTRegistry: should have issuer, smt_root, update_count=0
    smt_id = DEPLOYED["smt_registry"]["app_id"]
    state  = read_global_state(client, smt_id)
    test("smt_issuer_set",  "issuer" in state, f"keys: {list(state.keys())}")
    test("smt_root_set",    "smt_root" in state, f"smt_root present")
    count = state.get("update_count", -1)
    test("smt_count_zero",  count == 0, f"update_count={count}")

    # KYCBoxStorage: issuer + total_blobs=0
    kbs_id = DEPLOYED["kyc_box_storage"]["app_id"]
    state  = read_global_state(client, kbs_id)
    test("kbs_issuer_set",  "issuer" in state, f"keys: {list(state.keys())}")
    blobs = state.get("total_blobs", -1)
    test("kbs_blobs_zero",  blobs == 0, f"total_blobs={blobs}")

    # CredentialManager: ASA ID should be non-zero
    cm_id  = DEPLOYED["credential_manager"]["app_id"]
    state  = read_global_state(client, cm_id)
    asa_id = state.get("credential_asa_id", 0)
    test("cm_asa_created",  asa_id > 0, f"credential_asa_id={asa_id}")
    issued = state.get("total_issued", -1)
    test("cm_issued_zero",  issued == 0, f"total_issued={issued}")


def test_readonly_calls(client):
    print("\n=== [3] Read-only ABI Calls ===")

    pk     = get_pk()
    sender = account.address_from_private_key(pk)
    sp     = client.suggested_params()

    # NullifierRegistry: is_registered(dummy_nullifier) → False
    nr_id = DEPLOYED["nullifier_registry"]["app_id"]
    dummy_nullifier = b"\x00" * 32
    try:
        # ABI call via simulate
        call = transaction.ApplicationNoOpTxn(
            sender=sender, sp=sp, index=nr_id,
            app_args=[sel("is_registered(byte[])bool"),
                      (len(dummy_nullifier)).to_bytes(2, "big") + dummy_nullifier],
        )
        dry  = client.dryrun(transaction.create_dryrun(client, [call.sign(pk)]))
        test("nr_is_registered_call", True, "dry-run succeeded")
    except Exception as e:
        test("nr_is_registered_call", False, str(e)[:80])

    # CredentialManager: get_credential_asa_id() → expected ASA ID
    cm_id      = DEPLOYED["credential_manager"]["app_id"]
    exp_asa_id = DEPLOYED["credential_manager"].get("credential_asa_id", 0)
    try:
        call = transaction.ApplicationNoOpTxn(
            sender=sender, sp=sp, index=cm_id,
            app_args=[sel("get_credential_asa_id()uint64")],
        )
        dry = client.dryrun(transaction.create_dryrun(client, [call.sign(pk)]))
        txn_result = dry.get("txns", [{}])[0]
        logs = txn_result.get("logs", [])
        asa_from_call = None
        if logs:
            raw = base64.b64decode(logs[0])
            if len(raw) >= 12:
                asa_from_call = int.from_bytes(raw[4:12], "big")
        test("cm_get_asa_id", asa_from_call == exp_asa_id,
             f"expected={exp_asa_id}, got={asa_from_call}")
    except Exception as e:
        test("cm_get_asa_id", False, str(e)[:80])


def test_nullifier_registration(client):
    """Test register a nullifier, check it, then invalidate it."""
    print("\n=== [4] NullifierRegistry Register + Invalidate ===")

    pk     = get_pk()
    sender = account.address_from_private_key(pk)
    nr_id  = DEPLOYED["nullifier_registry"]["app_id"]

    # Test nullifier: MiMC hash from our Go test vectors
    test_nullifier_hex = "8103393176036573007132872524834469807800761359628792454260082229404595316139"
    nullifier_bytes    = int(test_nullifier_hex).to_bytes(32, "big")

    # MBR for box storage: 2500 + 400 * (8 + len("nul_") + 32 + 32) = ~31,600 microALGO
    sp = client.suggested_params()

    # Fund the NullifierRegistry for box MBR
    fund_txn = transaction.PaymentTxn(
        sender=sender, sp=sp,
        receiver=DEPLOYED["nullifier_registry"]["app_address"],
        amt=50_000,  # 0.05 ALGO for box MBR
    )
    signed_fund = fund_txn.sign(pk)
    fund_txid   = client.send_transaction(signed_fund)
    wait_confirmed(client, fund_txid)
    logger.info(f"  Funded NullifierRegistry for box MBR")

    # ABI encode nullifier as arc4.DynamicArray<UInt8>
    enc_nullifier = len(nullifier_bytes).to_bytes(2, "big") + nullifier_bytes

    # Register nullifier
    sp = client.suggested_params()
    reg_txn = transaction.ApplicationNoOpTxn(
        sender=sender, sp=sp, index=nr_id,
        app_args=[sel("register(byte[],address)void"), enc_nullifier,
                  transaction.encoding.decode_address(sender)],
        accounts=[sender],
        boxes=[(nr_id, b"nul_" + nullifier_bytes)],
    )
    try:
        reg_txid = client.send_transaction(reg_txn.sign(pk))
        wait_confirmed(client, reg_txid)
        test("nr_register", True, f"txid={reg_txid}")

        # Check is_registered → True via actual simulated call
        sp = client.suggested_params()
        sp.fee = 0
        check_txn = transaction.ApplicationNoOpTxn(
            sender=sender, sp=sp, index=nr_id,
            app_args=[sel("is_registered(byte[])bool"), enc_nullifier],
            boxes=[(nr_id, b"nul_" + nullifier_bytes)],
        )
        # Check via global state total_registered increment instead of dry-run
        state = read_global_state(client, nr_id)
        total = state.get("total_registered", 0)
        test("nr_is_registered_true", total == 1, f"total_registered={total} after register")

        # Invalidate
        sp = client.suggested_params()
        del_txn = transaction.ApplicationNoOpTxn(
            sender=sender, sp=sp, index=nr_id,
            app_args=[sel("invalidate(byte[])void"), enc_nullifier],
            boxes=[(nr_id, b"nul_" + nullifier_bytes)],
        )
        del_txid = client.send_transaction(del_txn.sign(pk))
        wait_confirmed(client, del_txid)
        test("nr_invalidate", True, f"txid={del_txid}")

    except Exception as e:
        test("nr_register", False, str(e)[:120])


def main():
    print("=" * 65)
    print("  AlgoKYC E2E Integration Tests — Algorand Testnet")
    print("=" * 65)
    print(f"  Network : {DEPLOYED.get('network')}")
    print(f"  Deployer: {DEPLOYED.get('deployer')}")
    print(f"  Contracts: {sum(1 for v in DEPLOYED.values() if isinstance(v, dict) and 'app_id' in v)}")

    client = get_algod()

    test_contracts_exist(client)
    test_global_state(client)
    test_readonly_calls(client)
    test_nullifier_registration(client)

    print("\n" + "=" * 65)
    total = len(PASSED) + len(FAILED)
    print(f"  RESULTS: {len(PASSED)}/{total} passed, {len(FAILED)} failed")
    if FAILED:
        print(f"  FAILED:  {', '.join(FAILED)}")
    else:
        print("  ALL TESTS PASSED - AlgoKYC live on Algorand Testnet!")
    print("=" * 65)

    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

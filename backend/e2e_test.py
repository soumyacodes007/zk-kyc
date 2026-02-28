"""
e2e_test.py — AlgoKYC Full End-to-End Test Suite
=================================================
Tests every layer of the system:
  1. Backend health + config
  2. ECIES key derivation (encrypt → decrypt round-trip)
  3. Shamir 3-of-5 split → reconstruct round-trip
  4. Court order lifecycle (create → vote → approve → decrypt)
  5. Algorand testnet API reachability + NullifierRegistry status
  6. Backend API endpoints (health, pubkey, contracts, verify, nullifier)
  7. Full court order REST flow (via requests)

Run with:
  python e2e_test.py
"""
import json, sys, time, traceback

# Force UTF-8 output on Windows (avoids cp1252 encoding errors)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
INFO = "[INFO]"

results = []

def test(name, fn):
    try:
        result = fn()
        print(f"  {PASS}  {name}")
        if result: print(f"       {result}")
        results.append((name, True, None))
    except Exception as e:
        print(f"  {FAIL}  {name}")
        print(f"       {e}")
        results.append((name, False, str(e)))

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. Config ────────────────────────────────────────────────────────────────

section("1. Configuration & Environment")

def test_config():
    import sys; sys.path.insert(0, ".")
    from config import get_settings
    s = get_settings()
    assert s.nullifier_registry_id == 756272073, f"Wrong NR ID: {s.nullifier_registry_id}"
    assert s.deployer_mnemonic, "deployer_mnemonic is empty"
    assert s.issuer_private_key_hex, "issuer_private_key_hex is empty"
    return f"NullifierRegistry={s.nullifier_registry_id}, deployer={s.deployer_mnemonic[:12]}..."

test("Config loads from .env", test_config)


# ── 2. ECIES Encryption ──────────────────────────────────────────────────────

section("2. ECIES Encryption / Decryption Round-trip")

def test_ecies_keygen():
    from ecies_service import load_or_generate_issuer_key, get_public_key_hex
    from config import get_settings
    privkey = load_or_generate_issuer_key(get_settings().issuer_private_key_hex)
    pubkey  = get_public_key_hex(privkey)
    assert len(privkey) == 32, f"privkey must be 32 bytes, got {len(privkey)}"
    assert len(pubkey) == 130, f"pubkey must be 65-byte uncompressed (130 hex chars), got {len(pubkey)}"
    assert pubkey.startswith("04"), "pubkey must be uncompressed (04 prefix)"
    return f"privkey={privkey.hex()[:12]}... pubkey={pubkey[:16]}..."

test("ECIES key generation", test_ecies_keygen)

def test_ecies_roundtrip():
    from ecies_service import (load_or_generate_issuer_key, get_public_key_hex,
                                encrypt_identity, decrypt_identity)
    from config import get_settings
    privkey = load_or_generate_issuer_key(get_settings().issuer_private_key_hex)
    pubkey  = get_public_key_hex(privkey)

    identity = {"name": "Ravi Kumar", "dob": "01-01-1990", "state": "Karnataka", "test": True}
    encrypted = encrypt_identity(pubkey, identity)
    assert len(encrypted) > 0, "Encrypted blob is empty"
    assert isinstance(encrypted, str), "Should be hex string"

    # Decrypt
    decrypted = decrypt_identity(privkey, encrypted)
    assert decrypted["name"] == "Ravi Kumar", f"Name mismatch: {decrypted}"
    assert decrypted["state"] == "Karnataka", f"State mismatch"
    assert "error" not in decrypted, f"Decrypt error: {decrypted}"
    return f"Encrypted {len(encrypted)//2}B → decrypted OK (name={decrypted['name']})"

test("ECIES encrypt → decrypt round-trip", test_ecies_roundtrip)


# ── 3. Shamir Secret Sharing ─────────────────────────────────────────────────

section("3. Shamir 3-of-5 Secret Sharing")

def test_shamir_split_3of5():
    from shamir_service import split_secret, reconstruct_secret, shares_to_hex, hex_to_shares
    import os
    secret = os.urandom(32)
    shares = split_secret(secret, n=5, k=3)

    assert len(shares) == 5, f"Expected 5 shares, got {len(shares)}"

    # Reconstruct with first 3
    rec = reconstruct_secret(shares[:3])
    assert rec == secret, f"3-of-5 reconstruction failed!\n  original: {secret.hex()}\n  got:      {rec.hex()}"
    return f"secret={secret.hex()[:12]}... split into 5 shares, reconstructed with 3 ✓"

test("Shamir split and reconstruct (3-of-5)", test_shamir_split_3of5)

def test_shamir_any_3():
    from shamir_service import split_secret, reconstruct_secret
    import os
    secret = os.urandom(32)
    shares = split_secret(secret, n=5, k=3)

    # Reconstruct with shares [1,3,5] (non-consecutive)
    chosen = [shares[0], shares[2], shares[4]]
    rec = reconstruct_secret(chosen)
    assert rec == secret, f"Reconstruction with shares 1,3,5 failed!"
    return f"Shares 1,3,5 (non-consecutive) → correct reconstruction"

test("Shamir reconstruct with non-consecutive shares (1,3,5)", test_shamir_any_3)

def test_shamir_hex_roundtrip():
    from shamir_service import split_secret, reconstruct_secret, shares_to_hex, hex_to_shares
    import os
    secret = os.urandom(32)
    shares     = split_secret(secret, n=5, k=3)
    hex_shares = shares_to_hex(shares)
    parsed     = hex_to_shares(hex_shares)
    rec        = reconstruct_secret(parsed[:3])
    assert rec == secret, "Hex serialization round-trip failed"
    return "split → hex → parse → reconstruct ✓"

test("Shamir hex serialization round-trip", test_shamir_hex_roundtrip)

def test_shamir_ecies_combined():
    """Full: split ECIES key → distribute shares → reconstruct → decrypt"""
    from shamir_service import split_secret, reconstruct_secret, shares_to_hex, hex_to_shares
    from ecies_service import (load_or_generate_issuer_key, get_public_key_hex,
                                encrypt_identity, decrypt_identity)
    from config import get_settings

    privkey = load_or_generate_issuer_key(get_settings().issuer_private_key_hex)
    pubkey  = get_public_key_hex(privkey)

    # Encrypt identity
    identity  = {"name": "Priya Singh", "dob": "15-06-1992", "uid_masked": "1234****5678"}
    encrypted = encrypt_identity(pubkey, identity)

    # Split private key into 5 shares
    shares     = split_secret(privkey, n=5, k=3)
    hex_shares = shares_to_hex(shares)

    # Simulate 3 custodians submitting their shares
    custodian_shares = hex_to_shares([hex_shares[0], hex_shares[2], hex_shares[4]])  # 1,3,5
    rec_key = reconstruct_secret(custodian_shares)
    assert rec_key == privkey, "Key reconstruction mismatch"

    # Decrypt with reconstructed key
    decrypted = decrypt_identity(rec_key, encrypted)
    assert decrypted["name"] == "Priya Singh"
    return f"Shamir 3-of-5 + ECIES decrypt ✓ (identity: {decrypted['name']})"

test("Shamir 3-of-5 + ECIES combined (court order simulation)", test_shamir_ecies_combined)


# ── 4. Court Order Service ───────────────────────────────────────────────────

section("4. Court Order Lifecycle (in-memory)")

def test_court_order_full():
    from court_order_service import (create_court_order, cast_vote, get_order,
                                     init_shamir_shares, CourtOrderStatus)
    from shamir_service import split_secret, shares_to_hex, generate_issuer_key
    from ecies_service import (load_or_generate_issuer_key, get_public_key_hex,
                                encrypt_identity)
    from config import get_settings

    # Init Shamir shares
    privkey    = load_or_generate_issuer_key(get_settings().issuer_private_key_hex)
    pubkey     = get_public_key_hex(privkey)
    shares     = split_secret(privkey, n=5, k=3)
    hex_shares = shares_to_hex(shares)
    init_shamir_shares(hex_shares)

    # Encrypt identity blob
    identity  = {"name": "Test User", "dob": "01-01-1990"}
    blob = encrypt_identity(pubkey, identity)

    # Create court order
    order = create_court_order(
        nullifier_hex="a" * 64,
        reason="Test court order #2024-001",
        encrypted_blob=blob,
    )
    assert order.status == CourtOrderStatus.PENDING

    # Vote: 2 custodians approve
    order = cast_vote(order.id, "custodian-wallet-1", 1, True, "Reviewed docs")
    assert order.status == CourtOrderStatus.PENDING, "Should still be pending after 1 vote"

    order = cast_vote(order.id, "custodian-wallet-2", 2, True, "Case verified")
    assert order.status == CourtOrderStatus.PENDING, "Should still be pending after 2 votes"

    # 3rd vote tips the balance
    order = cast_vote(order.id, "custodian-wallet-3", 3, True, "Approved")
    assert order.status == CourtOrderStatus.APPROVED, f"Expected APPROVED, got {order.status}"
    assert order.decrypted_identity is not None, "Identity should be decrypted"
    assert order.decrypted_identity.get("name") == "Test User", f"Wrong identity: {order.decrypted_identity}"

    return (f"Order {order.id}: PENDING→APPROVED, identity decrypted: "
            f"{order.decrypted_identity.get('name')}")

test("Full court order lifecycle (create → 3 votes → approve → decrypt)", test_court_order_full)

def test_court_order_reject():
    from court_order_service import (create_court_order, cast_vote, CourtOrderStatus)
    order = create_court_order("b"*64, "Test rejection")
    cast_vote(order.id, "c1", 1, False)
    cast_vote(order.id, "c2", 2, False)
    cast_vote(order.id, "c3", 3, False)
    assert order.status == CourtOrderStatus.REJECTED, f"Expected REJECTED, got {order.status}"
    return "3 rejections → REJECTED ✓"

test("Court order rejection (3 rejections)", test_court_order_reject)


# ── 5. Algorand Testnet ──────────────────────────────────────────────────────

section("5. Algorand Testnet Connectivity")

def test_algod_reachable():
    import urllib.request
    url = "https://testnet-api.algonode.cloud/v2/status"
    req = urllib.request.urlopen(url, timeout=10)
    data = json.loads(req.read())
    round_num = data.get("last-round", 0)
    assert round_num > 0, f"Invalid round: {round_num}"
    return f"Testnet round #{round_num:,}"

test("Algorand Testnet (algonode.cloud) reachable", test_algod_reachable)

def test_nr_app_state():
    from algorand_service import get_kyc_status
    data = get_kyc_status(756272073)
    assert "total_registered" in data, f"Missing total_registered: {data}"
    return f"NullifierRegistry app_id=756272073, total_registered={data['total_registered']}"

test("NullifierRegistry global state readable", test_nr_app_state)


# ── 6. Backend HTTP API ──────────────────────────────────────────────────────

section("6. Backend API Endpoints (live HTTP)")

def test_http(name, path, method="GET", body=None, headers=None, expected_key=None, api_key=None):
    import urllib.request, urllib.error
    url = f"http://localhost:8000{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    data = json.dumps(body).encode() if body else None
    try:
        resp = urllib.request.urlopen(req, data=data, timeout=10)
        result = json.loads(resp.read())
        if expected_key:
            assert expected_key in result, f"Missing '{expected_key}' in {result}"
        return result
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        raise AssertionError(f"HTTP {e.code}: {raw[:200]}")

def test_health_endpoint():
    r = test_http("health", "/health", expected_key="status")
    assert r["status"] == "ok"
    assert r["network"] == "testnet"
    return f"status={r['status']} network={r['network']}"

test("GET /health", test_health_endpoint)

def test_pubkey_endpoint():
    r = test_http("pubkey", "/api/v1/issuer/pubkey", expected_key="pubkey_hex")
    assert r["bytes"] == 65, f"Expected 65 bytes, got {r['bytes']}"
    assert r["pubkey_hex"].startswith("04"), "Must be uncompressed pubkey"
    return f"pubkey={r['pubkey_hex'][:16]}... ({r['bytes']}B)"

test("GET /api/v1/issuer/pubkey", test_pubkey_endpoint)

def test_contracts_endpoint():
    r = test_http("contracts", "/api/v1/contracts", expected_key="nullifier_registry")
    assert r["nullifier_registry"]["app_id"] == 756272073
    return f"4 contracts: NR={r['nullifier_registry']['app_id']}"

test("GET /api/v1/contracts", test_contracts_endpoint)

def test_verify_endpoint():
    r = test_http("verify", "/api/v1/verify/6AUBAIKBTNH5VEGMXRXLXQW5RRXFKQ3JAQ3YSNONY4Z2LIFO6HETGQ7DTM", expected_key="is_verified")
    return f"is_verified={r['is_verified']} total_registered={r['total_registered']}"

test("GET /api/v1/verify/{wallet}", test_verify_endpoint)

def test_nullifier_endpoint():
    r = test_http("nullifier", "/api/v1/nullifier/" + "a"*64, expected_key="is_registered")
    return f"is_registered={r['is_registered']}"

test("GET /api/v1/nullifier/{hex}", test_nullifier_endpoint)

def test_court_order_api():
    ISSUER_KEY = "algokyc-dev-secret-change-in-production"
    # Create order
    r = test_http("create_order", "/api/v1/court-order", "POST",
        body={"nullifier_hex": "c"*64, "reason": "e2e test order"},
        api_key=ISSUER_KEY, expected_key="order_id")
    order_id = r["order_id"]

    # List orders
    orders = test_http("list", "/api/v1/court-orders")
    assert isinstance(orders, list), "Expected list"

    # Get order
    o = test_http("get", f"/api/v1/court-order/{order_id}", expected_key="status")
    assert o["status"] == "pending"

    # Vote
    v = test_http("vote", f"/api/v1/court-order/{order_id}/vote", "POST",
        body={"custodian_id": "e2e-custodian-1", "custodian_num": 1, "approved": True, "note": "e2e test"})
    return f"order={order_id[:8]}... created, listed, fetched, voted ✓ approvals={v.get('approvals', '?')}"

test("Court order API (create → list → get → vote)", test_court_order_api)


# ── 7. Widget / Dashboard builds ─────────────────────────────────────────────

section("7. Frontend Build Check")

import subprocess, os

def test_widget_build():
    r = subprocess.run(
        "npm run build",
        capture_output=True, text=True, shell=True,
        cwd=os.path.abspath("../widget"), timeout=90
    )
    if r.returncode != 0:
        raise AssertionError(f"Widget build failed:\n{r.stderr[-500:] or r.stdout[-500:]}")
    return "widget/ vite build: OK"

def test_dashboard_build():
    r = subprocess.run(
        "npm run build",
        capture_output=True, text=True, shell=True,
        cwd=os.path.abspath("../dashboard"), timeout=90
    )
    if r.returncode != 0:
        raise AssertionError(f"Dashboard build failed:\n{r.stderr[-500:] or r.stdout[-500:]}")
    return "dashboard/ vite build: OK"

test("Widget (Vite) production build", test_widget_build)
test("Dashboard (Vite) production build", test_dashboard_build)


# ── Summary ──────────────────────────────────────────────────────────────────

section("RESULTS")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)

print(f"\n  Passed: {passed}/{total}")
if failed:
    print(f"  Failed: {failed}/{total}")
    print("\n  Failures:")
    for name, ok, err in results:
        if not ok:
            print(f"    • {name}: {err}")

print()
sys.exit(0 if failed == 0 else 1)

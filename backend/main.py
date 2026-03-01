"""
main.py — AlgoKYC Backend API
==============================
FastAPI backend that acts as the issuer for the AlgoKYC system.

Architecture:
  Browser (user) → generates ZK proof locally → sends to this backend
  This backend   → verifies proof → registers nullifier on Algorand Testnet
  dApps          → call GET /verify/{wallet} to check KYC status

Endpoints:
  POST /api/v1/register           — verify proof + register nullifier on-chain
  GET  /api/v1/verify/{wallet}    — check KYC status for a wallet
  GET  /api/v1/nullifier/{hex}    — check if specific nullifier is registered
  POST /api/v1/revoke             — issuer-only revocation (requires API key)
  GET  /api/v1/contracts          — deployed contract addresses
  GET  /health                    — health check
"""
import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import Settings, get_settings
from zk_verifier import verify_groth16_proof
from algorand_service import (
    get_kyc_status,
    is_nullifier_registered,
    register_nullifier,
    invalidate_nullifier,
)
from ecies_service import (
    load_or_generate_issuer_key,
    get_public_key_hex,
    encrypt_identity,
    decrypt_identity,
    store_identity_blob,
    get_identity_blob,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("algokyc.api")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AlgoKYC Issuer Backend",
    description=(
        "Zero-Knowledge KYC issuer backend for Algorand. "
        "Verifies Groth16 proofs and registers nullifiers on-chain."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — must be at module level before startup
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ECIES Issuer Key ──────────────────────────────────────────────────────────
_issuer_privkey = load_or_generate_issuer_key(_settings.issuer_private_key_hex)
_issuer_pubkey_hex = get_public_key_hex(_issuer_privkey)
logger.info(f"Issuer public key: {_issuer_pubkey_hex[:20]}… ({len(_issuer_pubkey_hex)//2} bytes)")


# ── Request / Response Models ──────────────────────────────────────────────────

class Groth16ProofModel(BaseModel):
    pi_a: list[str]
    pi_b: list[list[str]]
    pi_c: list[str]
    protocol: str = "groth16"
    curve: str = "bn128"


class RegisterRequest(BaseModel):
    """
    Sent by the browser after generating a ZK proof locally.
    Private inputs (aadhaarHash, walletSecret) are NEVER included here.
    encrypted_blob: ECIES-encrypted identity JSON (hex). Contains name, DOB, etc.
    Encrypted with the issuer's secp256k1 public key — only decryptable via
    3-of-5 Shamir reconstruction during an approved court order.
    """
    proof: Groth16ProofModel = Field(..., description="Groth16 proof from snarkjs")
    public_signals: list[str] = Field(..., description="Public signals: [nullifier, merkleRoot, appId, isIndian, isAdult, isKYCVerified, ...constants]")
    wallet_address: str = Field(..., description="User's Algorand wallet address to bind the credential")
    encrypted_blob: str | None = Field(None, description="ECIES-encrypted identity JSON hex (encrypted with issuer pubkey in browser)")


class RegisterResponse(BaseModel):
    success: bool
    txid: str | None = None
    nullifier_hex: str | None = None
    explorer_url: str | None = None
    error: str | None = None


class VerifyResponse(BaseModel):
    wallet: str
    is_verified: bool
    total_registered: int
    network: str = "testnet"
    nullifier_registry_id: int


class NullifierResponse(BaseModel):
    nullifier_hex: str
    is_registered: bool
    network: str = "testnet"


class RevokeRequest(BaseModel):
    nullifier_hex: str = Field(..., description="32-byte nullifier hex to revoke")
    reason: str = Field(..., description="Human-readable reason for revocation")


class RevokeResponse(BaseModel):
    success: bool
    txid: str | None = None
    nullifier_hex: str
    error: str | None = None


# ── Auth ──────────────────────────────────────────────────────────────────────

async def require_issuer_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
):
    """Dependency: verify issuer API key for protected endpoints."""
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid issuer API key — provide X-API-Key header",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — used by load balancers and monitoring."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "network": "testnet"}


@app.get("/api/v1/issuer/pubkey")
async def get_issuer_pubkey():
    """
    Return the issuer's secp256k1 public key (uncompressed, hex).
    The widget fetches this and uses it to ECIES-encrypt the identity
    before submitting the proof. The raw identity NEVER reaches the backend.
    Only the Shamir-reconstructed key (from 3/5 custodian approval) can decrypt.
    """
    return {
        "pubkey_hex": _issuer_pubkey_hex,
        "format": "secp256k1 uncompressed (04 || x || y)",
        "bytes": len(_issuer_pubkey_hex) // 2,
    }


@app.get("/api/v1/contracts")
async def get_contracts(settings: Settings = Depends(get_settings)):
    """Return all deployed contract IDs — useful for SDK initialization."""
    return {
        "network": "testnet",
        "nullifier_registry": {
            "app_id": settings.nullifier_registry_id,
            "explorer": f"https://allo.info/application/{settings.nullifier_registry_id}",
        },
        "smt_registry": {
            "app_id": settings.smt_registry_id,
            "explorer": f"https://allo.info/application/{settings.smt_registry_id}",
        },
        "kyc_box_storage": {
            "app_id": settings.kyc_box_storage_id,
            "explorer": f"https://allo.info/application/{settings.kyc_box_storage_id}",
        },
        "credential_manager": {
            "app_id": settings.credential_manager_id,
            "credential_asa_id": settings.credential_asa_id,
            "explorer": f"https://allo.info/application/{settings.credential_manager_id}",
        },
    }


@app.post("/api/v1/register", response_model=RegisterResponse)
async def register_kyc(
    req: RegisterRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Main KYC registration endpoint.

    Flow:
      1. Verify Groth16 ZK proof using snarkjs
      2. Extract + validate public signals (isIndian, isAdult, isKYCVerified, appId)
      3. Register nullifier on NullifierRegistry (Algorand Testnet)
      4. Return on-chain transaction ID

    Data policy:
      - Proof and public signals received here contain NO private data
      - aadhaarHash and walletSecret never leave the user's browser
      - The nullifier is a one-way hash: impossible to reverse to identity
    """
    logger.info(f"Registration request for wallet: {req.wallet_address}")

    # Load verification key (absolute path)
    backend_dir = Path(__file__).parent
    vk_path = (backend_dir.parent / "projects/circuits/circom/build/verification_key.json").resolve()
    
    if not vk_path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Verification key not configured — {vk_path}",
        )

    # 1. Verify ZK proof
    verify_result = verify_groth16_proof(
        verification_key_path=vk_path,
        public_signals=req.public_signals,
        proof=req.proof.model_dump(),
        expected_app_id=settings.nullifier_registry_id,
    )

    if not verify_result.valid:
        logger.warning(f"Proof verification failed: {verify_result.error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ZK proof verification failed: {verify_result.error}",
        )

    logger.info(f"Proof verified — nullifier: {verify_result.nullifier_hex}")

    # 2. Check for double-registration
    if is_nullifier_registered(
        verify_result.nullifier_hex,
        settings.nullifier_registry_id,
        settings.algod_server,
        settings.algod_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This identity is already registered (nullifier collision prevention)",
        )

    # 3. Register on-chain
    try:
        txid = register_nullifier(
            deployer_mnemonic=settings.deployer_mnemonic,
            nullifier_hex=verify_result.nullifier_hex,
            wallet_address=req.wallet_address,
            nr_app_id=settings.nullifier_registry_id,
            algod_server=settings.algod_server,
            algod_token=settings.algod_token,
        )
    except Exception as e:
        logger.error(f"On-chain registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"On-chain registration failed: {str(e)}",
        )

    explorer_url = f"https://allo.info/tx/{txid}"
    logger.info(f"Registration complete: {explorer_url}")

    # Store encrypted identity blob associated with this nullifier
    # (used by court order service for ECIES decrypt upon 3/5 custodian approval)
    if req.encrypted_blob:
        store_identity_blob(verify_result.nullifier_hex, req.encrypted_blob)
        logger.info(f"Encrypted identity blob stored ({len(req.encrypted_blob)//2}B) for nullifier {verify_result.nullifier_hex[:16]}…")
    else:
        logger.warning("No encrypted_blob provided — court orders will not be able to reveal identity")

    return RegisterResponse(
        success=True,
        txid=txid,
        nullifier_hex=verify_result.nullifier_hex,
        explorer_url=explorer_url,
    )


@app.get("/api/v1/verify/{wallet}", response_model=VerifyResponse)
async def verify_kyc(
    wallet: str,
    settings: Settings = Depends(get_settings),
):
    """
    Check KYC status for a wallet address.
    Used by dApps to gate access to KYC-verified users.

    Note: In V1, this queries total_registered on NullifierRegistry.
    V2 will query the box directly to check wallet-specific binding.
    """
    kyc_data = get_kyc_status(
        nr_app_id=settings.nullifier_registry_id,
        algod_server=settings.algod_server,
        algod_token=settings.algod_token,
    )
    return VerifyResponse(
        wallet=wallet,
        is_verified=kyc_data.get("total_registered", 0) > 0,
        total_registered=kyc_data.get("total_registered", 0),
        nullifier_registry_id=settings.nullifier_registry_id,
    )


@app.get("/api/v1/nullifier/{nullifier_hex}", response_model=NullifierResponse)
async def check_nullifier(
    nullifier_hex: str,
    settings: Settings = Depends(get_settings),
):
    """
    Check if a specific nullifier is registered on-chain.
    More precise than /verify/{wallet} — directly checks NullifierRegistry box storage.
    """
    registered = is_nullifier_registered(
        nullifier_hex=nullifier_hex,
        nr_app_id=settings.nullifier_registry_id,
        algod_server=settings.algod_server,
        algod_token=settings.algod_token,
    )
    return NullifierResponse(nullifier_hex=nullifier_hex, is_registered=registered)


@app.post(
    "/api/v1/revoke",
    response_model=RevokeResponse,
    dependencies=[Depends(require_issuer_key)],
)
async def revoke_credential(
    req: RevokeRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Revoke a KYC credential by invalidating its nullifier.
    ISSUER-ONLY — requires X-API-Key header.

    Use cases:
      - Court order requiring identity disclosure + revocation
      - Fraud detection
      - User-requested credential cancellation
    """
    logger.info(f"Revocation request for nullifier: {req.nullifier_hex} — reason: {req.reason}")

    # Verify nullifier exists before revoking
    if not is_nullifier_registered(
        req.nullifier_hex,
        settings.nullifier_registry_id,
        settings.algod_server,
        settings.algod_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nullifier {req.nullifier_hex} is not registered",
        )

    try:
        txid = invalidate_nullifier(
            deployer_mnemonic=settings.deployer_mnemonic,
            nullifier_hex=req.nullifier_hex,
            nr_app_id=settings.nullifier_registry_id,
            algod_server=settings.algod_server,
            algod_token=settings.algod_token,
        )
        logger.info(f"Credential revoked: txid={txid}")
        return RevokeResponse(success=True, txid=txid, nullifier_hex=req.nullifier_hex)
    except Exception as e:
        logger.error(f"Revocation failed: {e}")
        return RevokeResponse(success=False, nullifier_hex=req.nullifier_hex, error=str(e))


# ── Run ───────────────────────────────────────────────────────────────────────

# ── Court Order Endpoints ─────────────────────────────────────────────────────

from court_order_service import (
    create_court_order, get_order, list_orders, cast_vote,
    execute_revocation, get_custodian_share, init_shamir_shares,
    CourtOrderStatus,
)
from shamir_service import split_secret, shares_to_hex, generate_issuer_key


class CourtOrderCreateRequest(BaseModel):
    nullifier_hex: str = Field(..., description="Nullifier to revoke")
    reason: str = Field(..., description="Reason for court order")
    pdf_url: str | None = Field(None, description="Link to scanned court order PDF")
    encrypted_blob: str | None = Field(None, description="ECIES-encrypted identity hex")


class VoteRequest(BaseModel):
    custodian_id: str = Field(..., description="Custodian wallet address or ID")
    custodian_num: int = Field(..., ge=1, le=5, description="Custodian number 1-5")
    approved: bool = Field(..., description="True=approve, False=reject")
    note: str = Field("", description="Optional note")


class CourtOrderSummary(BaseModel):
    id: str
    nullifier_hex: str
    reason: str
    status: str
    created_at: float
    expires_at: float
    approvals: int
    rejections: int
    total_votes: int
    threshold: int = 3
    revoke_txid: str | None = None
    has_decrypted_identity: bool = False


def _order_to_summary(order) -> CourtOrderSummary:
    approvals  = sum(1 for v in order.votes if v.approved)
    rejections = sum(1 for v in order.votes if not v.approved)
    return CourtOrderSummary(
        id=order.id,
        nullifier_hex=order.nullifier_hex,
        reason=order.reason,
        status=order.status.value,
        created_at=order.created_at,
        expires_at=order.expires_at,
        approvals=approvals,
        rejections=rejections,
        total_votes=len(order.votes),
        revoke_txid=order.revoke_txid,
        has_decrypted_identity=order.decrypted_identity is not None,
    )


# Initialize Shamir shares at startup (split a test key for hackathon)
def _init_test_shamir(privkey_bytes: bytes):
    """Split the active ECIES key into 5 shares for the 5 custodians."""
    shares   = split_secret(privkey_bytes, n=5, k=3)
    hex_list = shares_to_hex(shares)
    init_shamir_shares(hex_list)
    logger.info("Shamir shares initialized for 5 custodians (3-of-5 threshold)")
    return privkey_bytes, hex_list

_issuer_key, _custodian_shares = _init_test_shamir(_issuer_privkey)


@app.get("/api/v1/custodian/{num}/share", dependencies=[Depends(require_issuer_key)])
async def get_share_for_custodian(num: int):
    """
    Issuer-only: return the Shamir share for custodian #{num}.
    In production: each share is delivered OOB (email/HSM), never via API.
    For hackathon demo only.
    """
    if num < 1 or num > 5:
        raise HTTPException(400, "Custodian number must be 1-5")
    share = get_custodian_share(num)
    return {"custodian_num": num, "share": share}


@app.post(
    "/api/v1/court-order",
    dependencies=[Depends(require_issuer_key)],
)
async def create_order(
    req: CourtOrderCreateRequest,
    settings: Settings = Depends(get_settings),
):
    """Create a new court order (issuer-only). Notifies 5 custodians to review."""
    order = create_court_order(
        nullifier_hex=req.nullifier_hex,
        reason=req.reason,
        pdf_url=req.pdf_url,
        encrypted_blob=req.encrypted_blob,
    )
    return {
        "order_id": order.id,
        "status": order.status.value,
        "message": "Court order created. 5 custodians must review — 3 approvals needed to proceed.",
        "expires_at": order.expires_at,
    }


@app.get("/api/v1/court-orders")
async def list_court_orders():
    """List all court orders (publicly readable — no sensitive data)."""
    return [_order_to_summary(o) for o in list_orders()]


@app.get("/api/v1/court-order/{order_id}")
async def get_court_order(order_id: str):
    """Get full court order details including votes."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, f"Court order {order_id} not found")

    summary = _order_to_summary(order)
    response = summary.model_dump()

    # Include decrypted identity IF it exists (in-memory, session only)
    if order.decrypted_identity:
        response["decrypted_identity"] = order.decrypted_identity
        response["identity_warning"] = (
            "⚠️  Identity data is in-memory only. Displayed ONCE then discarded. "
            "Do NOT log or store this data (DPDP compliance)."
        )
    # Include votes (without share data)
    response["votes"] = [
        {
            "custodian_id": v.custodian_id,
            "custodian_num": v.custodian_num,
            "approved": v.approved,
            "note": v.note,
            "timestamp": v.timestamp,
        }
        for v in order.votes
    ]
    return response


@app.post("/api/v1/court-order/{order_id}/vote")
async def vote_on_court_order(order_id: str, req: VoteRequest):
    """
    Custodian votes on a court order.
    On 3+ approvals, automatically reconstructs key and decrypts identity.
    Requires no auth for V1 (custodian identified by ID/wallet).
    """
    try:
        order = cast_vote(
            order_id=order_id,
            custodian_id=req.custodian_id,
            custodian_num=req.custodian_num,
            approved=req.approved,
            note=req.note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    approvals  = sum(1 for v in order.votes if v.approved)
    rejections = sum(1 for v in order.votes if not v.approved)

    return {
        "order_id": order_id,
        "status": order.status.value,
        "approvals": approvals,
        "rejections": rejections,
        "threshold_reached": order.status == CourtOrderStatus.APPROVED,
        "identity_decrypted": order.decrypted_identity is not None,
        "message": {
            CourtOrderStatus.PENDING:  f"Vote recorded. {approvals}/3 approvals so far.",
            CourtOrderStatus.APPROVED: f"✅ Threshold reached! Identity decrypted in-memory. Ready to execute revocation.",
            CourtOrderStatus.REJECTED: f"❌ Court order rejected ({rejections} rejections).",
        }.get(order.status, "Vote recorded."),
    }


@app.post(
    "/api/v1/court-order/{order_id}/execute",
    dependencies=[Depends(require_issuer_key)],
)
async def execute_court_order(
    order_id: str,
    settings: Settings = Depends(get_settings),
):
    """
    Execute an approved court order: revoke nullifier on Algorand Testnet.
    ISSUER-ONLY. Order must be in APPROVED status.
    """
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, "Court order not found")
    if order.status != CourtOrderStatus.APPROVED:
        raise HTTPException(400, f"Order is not approved (status={order.status.value})")

    try:
        txid = invalidate_nullifier(
            deployer_mnemonic=settings.deployer_mnemonic,
            nullifier_hex=order.nullifier_hex,
            nr_app_id=settings.nullifier_registry_id,
            algod_server=settings.algod_server,
            algod_token=settings.algod_token,
        )
        execute_revocation(order_id, txid)
        return {
            "success": True,
            "order_id": order_id,
            "txid": txid,
            "explorer_url": f"https://allo.info/tx/{txid}",
            "status": "executed",
            "message": "Nullifier invalidated on Algorand Testnet. Identity cleared from memory.",
        }
    except Exception as e:
        raise HTTPException(502, f"Revocation failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

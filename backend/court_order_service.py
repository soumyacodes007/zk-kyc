"""
court_order_service.py — Court Order lifecycle management
=========================================================
Handles the full revocation flow:
  1. Issuer creates a court order (with nullifier to revoke)
  2. 5 custodians each hold one Shamir share of the ECIES decrypt key
  3. When 3+ custodians approve, the key is reconstructed
  4. The encrypted identity blob is ECIES-decrypted in-memory
  5. The nullifier is invalidated on NullifierRegistry
  6. The decrypted identity is shown ONCE then discarded

In-memory store for V1 (no DB needed for hackathon).
"""
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

TOTAL_CUSTODIANS = 5
THRESHOLD = 3  # 3-of-5 required to reconstruct


class CourtOrderStatus(str, Enum):
    PENDING    = "pending"       # waiting for custodian approvals
    APPROVED   = "approved"      # ≥3 custodians approved → key reconstructed
    REJECTED   = "rejected"      # majority rejected
    EXECUTED   = "executed"      # nullifier revoked on-chain
    EXPIRED    = "expired"       # timed out without reaching threshold


@dataclass
class CustodianVote:
    custodian_id: str            # wallet address or custodian number
    custodian_num: int           # 1..5
    approved: bool
    share_hex: str               # their Shamir share (provided on approval)
    timestamp: float = field(default_factory=time.time)
    note: str = ""


@dataclass
class CourtOrder:
    id: str
    nullifier_hex: str           # nullifier to revoke
    encrypted_blob: str | None   # encrypted identity (hex) — to be decrypted on approval
    pdf_url: str | None          # URL to scanned court document
    reason: str
    created_at: float
    expires_at: float            # auto-expire after 48h
    status: CourtOrderStatus = CourtOrderStatus.PENDING
    votes: list[CustodianVote] = field(default_factory=list)
    decrypted_identity: dict | None = None   # in-memory only, never persisted
    revoke_txid: str | None = None


# ── In-memory store ───────────────────────────────────────────────────────────
# In production: replace with Redis or a DB
_orders: dict[str, CourtOrder] = {}

# Pre-split Shamir shares (set during startup or via init_shamir())
# _shamir_shares[custodian_num] = share_hex
_shamir_shares: dict[int, str] = {}


def init_shamir_shares(shares: list[str]) -> None:
    """
    Initialize Shamir shares for the 5 custodians.
    shares: list of 5 hex-encoded shares from shamir_service.split_secret()
    """
    from shamir_service import hex_to_shares
    parsed = hex_to_shares(shares)
    for idx, data in parsed:
        _shamir_shares[idx] = f"{idx}:{data.hex()}"
    logger.info(f"Initialized {len(_shamir_shares)} Shamir shares for custodians")


def get_custodian_share(custodian_num: int) -> str | None:
    """Get the Shamir share for a specific custodian (1..5)."""
    return _shamir_shares.get(custodian_num)


def create_court_order(
    nullifier_hex: str,
    reason: str,
    encrypted_blob: str | None = None,
    pdf_url: str | None = None,
    ttl_hours: int = 48,
) -> CourtOrder:
    order_id = secrets.token_hex(8)
    now = time.time()
    order = CourtOrder(
        id=order_id,
        nullifier_hex=nullifier_hex,
        encrypted_blob=encrypted_blob,
        pdf_url=pdf_url,
        reason=reason,
        created_at=now,
        expires_at=now + ttl_hours * 3600,
    )
    _orders[order_id] = order
    logger.info(f"Court order created: {order_id} for nullifier {nullifier_hex[:16]}...")
    return order


def get_order(order_id: str) -> CourtOrder | None:
    order = _orders.get(order_id)
    if order and time.time() > order.expires_at and order.status == CourtOrderStatus.PENDING:
        order.status = CourtOrderStatus.EXPIRED
    return order


def list_orders() -> list[CourtOrder]:
    return list(_orders.values())


def cast_vote(
    order_id: str,
    custodian_id: str,
    custodian_num: int,
    approved: bool,
    note: str = "",
) -> CourtOrder:
    """
    Record a custodian's vote on a court order.
    If approved and they provide their Shamir share, it's included.
    """
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Court order {order_id} not found")
    if order.status != CourtOrderStatus.PENDING:
        raise ValueError(f"Court order is not pending (status={order.status})")
    if time.time() > order.expires_at:
        order.status = CourtOrderStatus.EXPIRED
        raise ValueError("Court order has expired")

    # Check for duplicate vote
    existing_voters = {v.custodian_id for v in order.votes}
    if custodian_id in existing_voters:
        raise ValueError(f"Custodian {custodian_id} has already voted")

    # Get this custodian's Shamir share (only if approving)
    share_hex = ""
    if approved:
        share_hex = _shamir_shares.get(custodian_num, "")
        if not share_hex:
            logger.warning(f"No Shamir share found for custodian #{custodian_num}")

    vote = CustodianVote(
        custodian_id=custodian_id,
        custodian_num=custodian_num,
        approved=approved,
        share_hex=share_hex,
        note=note,
    )
    order.votes.append(vote)
    logger.info(f"Vote cast: order={order_id} custodian={custodian_num} approved={approved}")

    # Check thresholds
    approvals = [v for v in order.votes if v.approved]
    rejections = [v for v in order.votes if not v.approved]

    if len(approvals) >= THRESHOLD:
        order.status = CourtOrderStatus.APPROVED
        logger.info(f"Court order {order_id} APPROVED — {len(approvals)}/{TOTAL_CUSTODIANS} votes")
        _try_reconstruct_and_decrypt(order, approvals)

    elif len(rejections) > (TOTAL_CUSTODIANS - THRESHOLD):
        # Majority rejected (more than 2 rejections means it can never reach threshold)
        order.status = CourtOrderStatus.REJECTED
        logger.info(f"Court order {order_id} REJECTED — {len(rejections)} rejections")

    return order


def _try_reconstruct_and_decrypt(order: CourtOrder, approvals: list[CustodianVote]) -> None:
    """
    Reconstruct the ECIES key from Shamir shares and decrypt the identity blob.
    Called automatically when 3+ custodians approve.
    """
    from shamir_service import hex_to_shares, reconstruct_secret
    from ecies_service import decrypt_identity, get_identity_blob

    # Gather shares from approving custodians
    approval_shares = []
    for vote in approvals[:THRESHOLD]:  # take first k
        if vote.share_hex:
            approval_shares.append(vote.share_hex)

    if len(approval_shares) < THRESHOLD:
        logger.warning(f"Not enough shares to reconstruct: {len(approval_shares)}/{THRESHOLD}")
        return

    try:
        shares = hex_to_shares(approval_shares)
        reconstructed_key = reconstruct_secret(shares)
        logger.info(f"Key reconstructed: {reconstructed_key.hex()[:16]}... (in memory only)")

        # Find encrypted blob: prefer order's own blob, else look up by nullifier
        blob = order.encrypted_blob or get_identity_blob(order.nullifier_hex)

        if blob:
            order.decrypted_identity = decrypt_identity(reconstructed_key, blob)
            logger.info(f"Identity ECIES-decrypted in-memory for court order {order.id}")
        else:
            order.decrypted_identity = {
                "note": "No encrypted identity blob available. User may not have provided encrypted_blob during registration.",
                "nullifier": order.nullifier_hex,
            }
            logger.warning(f"No encrypted blob found for nullifier {order.nullifier_hex[:16]}...")

    except Exception as e:
        logger.error(f"Failed to reconstruct/decrypt for order {order.id}: {e}")
        order.decrypted_identity = {"error": str(e)}


def execute_revocation(order_id: str, txid: str) -> CourtOrder:
    """Mark court order as executed after on-chain revocation."""
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Court order {order_id} not found")
    order.status = CourtOrderStatus.EXECUTED
    order.revoke_txid = txid
    # Clear decrypted identity from memory after revocation
    order.decrypted_identity = None
    logger.info(f"Court order {order_id} EXECUTED — txid={txid}, identity cleared from memory")
    return order

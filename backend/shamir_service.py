"""
shamir_service.py — Shamir Secret Sharing (3-of-5 threshold)
===========================================================
Splits the issuer's ECIES private key into 5 shares.
When any 3 custodians provide their share, reconstructs the key.

For V1 hackathon:
  - Uses pure-Python GF(256) Shamir implementation
  - In production: use HSM + secure multi-party computation
  - Shares stored per-court-order in memory (custodian receives theirs via secure channel)

Math: Standard Shamir over GF(2^8) — each byte of the secret is shared independently.
"""
import os
import secrets
from dataclasses import dataclass, field


# ── GF(256) arithmetic (AES field: x^8 + x^4 + x^3 + x + 1) ─────────────────

PRIME = 257  # Shamir over GF(prime) with prime > 255

def _eval_poly(coefficients: list[int], x: int, prime: int) -> int:
    """Evaluate polynomial at x using Horner's method."""
    result = 0
    for coeff in reversed(coefficients):
        result = (result * x + coeff) % prime
    return result


def _lagrange_interpolate(x: int, x_s: list[int], y_s: list[int], prime: int) -> int:
    """Lagrange interpolation to recover f(x) given points (x_s, y_s)."""
    k = len(x_s)
    assert k == len(y_s), "Mismatched lengths"

    result = 0
    for i in range(k):
        num = y_s[i]
        for j in range(k):
            if j != i:
                num = num * (x - x_s[j]) % prime
        den = 1
        for j in range(k):
            if j != i:
                den = den * (x_s[i] - x_s[j]) % prime
        den_inv = pow(den, prime - 2, prime)
        result = (result + num * den_inv) % prime
    return result


def split_secret(secret_bytes: bytes, n: int = 5, k: int = 3) -> list[tuple[int, bytes]]:
    """
    Split secret_bytes into n shares, any k of which reconstruct the secret.
    Returns list of (share_index, share_bytes) tuples. Indexes are 1..n.

    Note: PRIME=257, so share values are in 0..256. We store each value as
    a 2-byte big-endian int so bytes() does not choke on 256.
    """
    share_bytes_list: list[list[int]] = [[] for _ in range(n)]

    for byte in secret_bytes:
        # Random polynomial of degree k-1 with f(0) = byte
        coeffs = [byte] + [secrets.randbelow(PRIME) for _ in range(k - 1)]
        for i in range(n):
            share_val = _eval_poly(coeffs, i + 1, PRIME)
            # Store as 2 bytes (big-endian) to safely hold values 0..256
            share_bytes_list[i].extend(share_val.to_bytes(2, 'big'))

    return [
        (i + 1, bytes(share_bytes_list[i]))
        for i in range(n)
    ]


def reconstruct_secret(shares: list[tuple[int, bytes]]) -> bytes:
    """
    Reconstruct the secret from k or more (index, share_bytes) tuples.
    Each share value is stored as 2-byte big-endian to handle GF(257) values (0-256).
    """
    if not shares:
        raise ValueError("No shares provided")

    # share_bytes has 2 bytes per secret byte → secret_len = len/2
    secret_len = len(shares[0][1]) // 2
    secret = []

    for byte_idx in range(secret_len):
        x_s = [s[0] for s in shares]
        # Parse each 2-byte big-endian value
        y_s = [int.from_bytes(s[1][byte_idx*2 : byte_idx*2+2], 'big') for s in shares]
        byte_val = _lagrange_interpolate(0, x_s, y_s, PRIME)
        secret.append(int(byte_val) % 256)

    return bytes(secret)


# ── Key management ────────────────────────────────────────────────────────────

def generate_issuer_key() -> bytes:
    """Generate a random 32-byte ECIES private key for the issuer."""
    return os.urandom(32)


def shares_to_hex(shares: list[tuple[int, bytes]]) -> list[str]:
    """Convert shares to hex strings for storage/transmission."""
    return [f"{idx}:{data.hex()}" for idx, data in shares]


def hex_to_shares(hex_shares: list[str]) -> list[tuple[int, bytes]]:
    """Parse hex_shares back to (index, bytes) tuples."""
    result = []
    for s in hex_shares:
        idx_str, data_hex = s.split(":", 1)
        result.append((int(idx_str), bytes.fromhex(data_hex)))
    return result

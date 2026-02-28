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
    nums = []
    dens = []
    for i in range(k):
        others = list(x_s)
        cur = others.pop(i)
        nums.append((-x_s[i] + x) % prime)  # unused — standard form
        # product(x - x_j) for j != i in numerator, denominator same
        nums_prod = 1
        dens_prod = 1
        for j in range(k):
            if j != i:
                nums_prod = (nums_prod * (x - x_s[j])) % prime
                dens_prod = (dens_prod * (x_s[i] - x_s[j])) % prime
        nums.append(nums_prod)
        dens.append(dens_prod)

    # Rebuild properly
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
        # Modular inverse of den
        den_inv = pow(den, prime - 2, prime)
        result = (result + num * den_inv) % prime
    return result


def split_secret(secret_bytes: bytes, n: int = 5, k: int = 3) -> list[tuple[int, bytes]]:
    """
    Split secret_bytes into n shares, any k of which reconstruct the secret.
    Returns list of (share_index, share_bytes) tuples. Indexes are 1..n.
    """
    shares = [(i, b"") for i in range(1, n + 1)]
    # Process each byte independently
    share_bytes_list: list[list[int]] = [[] for _ in range(n)]

    for byte in secret_bytes:
        # Random polynomial of degree k-1 with f(0) = byte
        coeffs = [byte] + [secrets.randbelow(PRIME) for _ in range(k - 1)]
        for i in range(n):
            share_val = _eval_poly(coeffs, i + 1, PRIME)
            # Store as 2 bytes since values can be up to PRIME-1 = 256
            share_bytes_list[i].append(share_val)

    return [
        (i + 1, bytes(share_bytes_list[i]))
        for i in range(n)
    ]


def reconstruct_secret(shares: list[tuple[int, bytes]]) -> bytes:
    """
    Reconstruct the secret from k or more (index, share_bytes) tuples.
    shares: list of (index, share_bytes) — at least k needed.
    """
    if not shares:
        raise ValueError("No shares provided")

    secret_len = len(shares[0][1])
    secret = []

    for byte_idx in range(secret_len):
        x_s = [s[0] for s in shares]
        y_s = [s[1][byte_idx] for s in shares]
        byte_val = _lagrange_interpolate(0, x_s, y_s, PRIME)
        secret.append(byte_val % 256)

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

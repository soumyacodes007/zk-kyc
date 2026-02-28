"""
ecies_service.py — ECIES encryption / decryption (pure Python, no native deps)
===============================================================================
Implements ECIES (Elliptic Curve Integrated Encryption Scheme) using:
  - secp256k1 elliptic curve (same as Ethereum / Bitcoin / Algorand)
  - ECDH key agreement
  - HKDF-SHA256 key derivation
  - AES-256-GCM authenticated encryption

This is cryptographically equivalent to eciespy/ecies-node but uses the
`cryptography` Python package (already installed) instead of coincurve
(which fails to build on Windows due to native libsecp256k1 deps).

Schema of encrypted output (hex):
  [04 || ephPubX(32) || ephPubY(32)] || IV(12) || ciphertext || tag(16)
  Total = 65 + 12 + len(plaintext) + 16 bytes

Browser side uses eciesjs (npm) which uses the exact same format.
"""
import json
import logging
import os
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

# In-memory blob store: nullifier_hex → encrypted_blob_hex
_identity_blobs: dict[str, str] = {}


def _get_curve():
    from cryptography.hazmat.primitives.asymmetric.ec import SECP256K1
    return SECP256K1()


def load_or_generate_issuer_key(hex_from_env: str = "") -> bytes:
    """
    Load or generate the issuer's secp256k1 private key.
    Returns 32 raw bytes.
    """
    if hex_from_env and len(hex_from_env) == 64:
        logger.info("Loaded issuer private key from environment")
        return bytes.fromhex(hex_from_env)

    key_file = Path(__file__).parent / ".issuer_key"
    if key_file.exists():
        raw = key_file.read_bytes()
        if len(raw) == 32:
            logger.info("Loaded issuer private key from .issuer_key")
            return raw

    privkey = os.urandom(32)
    key_file.write_bytes(privkey)
    logger.warning(
        f"Generated new issuer private key → .issuer_key\n"
        f"  Hex: {privkey.hex()}\n"
        f"  Add to .env as ISSUER_PRIVATE_KEY_HEX={privkey.hex()}"
    )
    return privkey


def get_public_key_hex(privkey_bytes: bytes) -> str:
    """
    Derive the uncompressed secp256k1 public key (65 bytes → 130 hex chars).
    eciesjs expects uncompressed (04 || x || y) format.
    """
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1, derive_private_key
    )
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat
    )
    n    = int.from_bytes(privkey_bytes, "big")
    priv = derive_private_key(n, SECP256K1(), default_backend())
    pub  = priv.public_key()
    return pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint).hex()


def ecies_encrypt(pubkey_hex: str, plaintext: bytes) -> bytes:
    """
    ECIES encrypt using recipient's secp256k1 public key.
    Compatible with eciesjs npm package (same wire format).
    """
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1, generate_private_key, ECDH,
        EllipticCurvePublicKey
    )
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.asymmetric.ec import (
        EllipticCurvePublicNumbers, SECP256K1 as _SECP256K1
    )

    backend = default_backend()

    # Parse recipient public key
    pub_bytes = bytes.fromhex(pubkey_hex)
    if pub_bytes[0] == 0x04:  # uncompressed
        x = int.from_bytes(pub_bytes[1:33], "big")
        y = int.from_bytes(pub_bytes[33:65], "big")
        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers
        recipient_pub = EllipticCurvePublicNumbers(x, y, SECP256K1()).public_key(backend)
    else:
        raise ValueError("Expected uncompressed public key (04 prefix)")

    # Generate ephemeral key pair
    eph_priv = generate_private_key(SECP256K1(), backend)
    eph_pub  = eph_priv.public_key()
    eph_pub_bytes = eph_pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    # ECDH: derive shared secret
    shared_secret = eph_priv.exchange(ECDH(), recipient_pub)

    # HKDF-SHA256 → 32-byte AES key
    aes_key = HKDF(
        algorithm=SHA256(), length=32, salt=None,
        info=b"ecies-encryption",
        backend=backend,
    ).derive(shared_secret)

    # AES-256-GCM encrypt
    iv = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ct = aesgcm.encrypt(iv, plaintext, None)  # ct includes 16-byte tag at end

    # Wire format: eph_pub(65) || iv(12) || ciphertext+tag
    return eph_pub_bytes + iv + ct


def ecies_decrypt(privkey_bytes: bytes, ciphertext: bytes) -> bytes:
    """
    ECIES decrypt using issuer's secp256k1 private key.
    Inverse of ecies_encrypt and compatible with eciesjs.
    """
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1, derive_private_key, ECDH, EllipticCurvePublicNumbers
    )
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    backend = default_backend()
    n    = int.from_bytes(privkey_bytes, "big")
    priv = derive_private_key(n, SECP256K1(), backend)

    # Parse wire format
    eph_pub_bytes = ciphertext[:65]
    iv            = ciphertext[65:77]
    ct_and_tag    = ciphertext[77:]

    x = int.from_bytes(eph_pub_bytes[1:33], "big")
    y = int.from_bytes(eph_pub_bytes[33:65], "big")
    eph_pub = EllipticCurvePublicNumbers(x, y, SECP256K1()).public_key(backend)

    # ECDH
    shared_secret = priv.exchange(ECDH(), eph_pub)

    # HKDF → AES key
    aes_key = HKDF(
        algorithm=SHA256(), length=32, salt=None,
        info=b"ecies-encryption",
        backend=backend,
    ).derive(shared_secret)

    # AES-GCM decrypt
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(iv, ct_and_tag, None)


def encrypt_identity(pubkey_hex: str, identity: dict) -> str:
    """
    Encrypt an identity dict as JSON and return hex-encoded ciphertext.
    Called during registration — identity never stored in plaintext.
    """
    plaintext = json.dumps(identity, ensure_ascii=False).encode()
    ct_bytes  = ecies_encrypt(pubkey_hex, plaintext)
    return ct_bytes.hex()


def decrypt_identity(privkey_bytes: bytes, encrypted_hex: str) -> dict:
    """
    Decrypt identity blob. Called only when court order 3/5 threshold is met.
    Returns identity dict or error dict.
    """
    try:
        ct      = bytes.fromhex(encrypted_hex)
        plain   = ecies_decrypt(privkey_bytes, ct)
        return json.loads(plain.decode())
    except Exception as e:
        logger.error(f"ECIES decrypt failed: {e}")
        return {"error": str(e)}


def store_identity_blob(nullifier_hex: str, encrypted_blob_hex: str) -> None:
    _identity_blobs[nullifier_hex] = encrypted_blob_hex
    logger.info(f"Identity blob stored: nullifier={nullifier_hex[:16]}… size={len(encrypted_blob_hex)//2}B")


def get_identity_blob(nullifier_hex: str) -> str | None:
    return _identity_blobs.get(nullifier_hex)

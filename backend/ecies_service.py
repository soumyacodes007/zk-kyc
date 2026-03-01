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
    ECIES encrypt matching the eciesjs npm package format.
    JS uses: 16-byte nonce, tag placed before ciphertext, and HKDF(senderPt || sharedPt).
    """
    from ecdsa import SECP256k1, SigningKey, VerifyingKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    import os

    # 1. Parse recipient public key (uncompressed)
    receiver_vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex)[1:], curve=SECP256k1)

    # 2. Generate ephemeral key
    eph_sk = SigningKey.generate(curve=SECP256k1)
    eph_pk_bytes = b'\x04' + eph_sk.privkey.public_key.point.x().to_bytes(32, 'big') + eph_sk.privkey.public_key.point.y().to_bytes(32, 'big')

    # 3. ECDH shared point
    shared_point = receiver_vk.pubkey.point * eph_sk.privkey.secret_multiplier
    shared_point_bytes = b'\x04' + shared_point.x().to_bytes(32, 'big') + shared_point.y().to_bytes(32, 'big')

    # 4. HKDF-SHA256 (eciesjs style: eph_pk || shared_point)
    hkdf_input = eph_pk_bytes + shared_point_bytes
    aes_key = HKDF(
        algorithm=SHA256(), length=32, salt=None, info=b"", backend=default_backend()
    ).derive(hkdf_input)

    # 5. AES-256-GCM symmetric encrypt (custom 16-byte nonce)
    iv = os.urandom(16)
    aesgcm = AESGCM(aes_key)
    # cryptography encrypts as iv || ct || tag
    encrypted = aesgcm.encrypt(iv, plaintext, None)
    
    # eciesjs expects tag (last 16 bytes of encrypted) BEFORE ciphertext
    tag = encrypted[-16:]
    ct = encrypted[:-16]

    # wire format: ephemeral_pk(65) || iv(16) || MAC_tag(16) || ciphertext
    return eph_pk_bytes + iv + tag + ct


def ecies_decrypt(privkey_bytes: bytes, ciphertext: bytes) -> bytes:
    """
    ECIES decrypt matching the eciesjs npm package format.
    """
    from ecdsa import SECP256k1, SigningKey, VerifyingKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend

    # 1. Parse wire format
    # eciesjs format: ephemeral_pub || iv(16) || MAC_tag(16) || ciphertext
    # The ephemeral pub key can be compressed (33 bytes) or uncompressed (65 bytes)
    first_byte = ciphertext[0]
    if first_byte == 0x04:
        pub_len = 65
    elif first_byte in (0x02, 0x03):
        pub_len = 33
    else:
        raise ValueError(f"Invalid public key prefix: {hex(first_byte)}")

    eph_pub_bytes = ciphertext[:pub_len]
    iv            = ciphertext[pub_len:pub_len+16]
    tag           = ciphertext[pub_len+16:pub_len+32]
    ct            = ciphertext[pub_len+32:]
    
    # 2. Rebuild standard GCM chunk (ct || tag)
    ct_and_tag = ct + tag

    # 3. ECDH shared point
    sk = SigningKey.from_string(privkey_bytes, curve=SECP256k1)
    
    # Process ephemeral public key
    if pub_len == 65:
        # Uncompressed
        vk = VerifyingKey.from_string(eph_pub_bytes[1:], curve=SECP256k1)
    else:
        # Compressed: we must parse the X coordinate and y-parity (0x02 = even, 0x03 = odd)
        import ecdsa
        vk = VerifyingKey.from_string(eph_pub_bytes, curve=SECP256k1)
    
    shared_point = vk.pubkey.point * sk.privkey.secret_multiplier
    shared_point_bytes = b'\x04' + shared_point.x().to_bytes(32, 'big') + shared_point.y().to_bytes(32, 'big')

    # 4. HKDF
    hkdf_input = eph_pub_bytes + shared_point_bytes
    aes_key = HKDF(
        algorithm=SHA256(), length=32, salt=None, info=b"", backend=default_backend()
    ).derive(hkdf_input)

    # 5. AES-GCM decrypt
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

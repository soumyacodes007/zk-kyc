import asyncio
import os
import sys

# add backend path so imports work
sys.path.append(os.path.abspath('backend'))

from config import get_settings
from ecies_service import ecies_encrypt, ecies_decrypt, get_public_key_hex, encrypt_identity, decrypt_identity

def test():
    settings = get_settings()
    priv_hex = settings.issuer_private_key_hex
    priv_bytes = bytes.fromhex(priv_hex)
    pub_hex = get_public_key_hex(priv_bytes)
    
    print(f"Pubkey: {pub_hex}")
    
    identity = {"name": "Test User", "dob": "1990-01-01"}
    ct_hex = encrypt_identity(pub_hex, identity)
    
    print(f"Encrypted blob len: {len(ct_hex)}")
    
    # Decrypt
    try:
        dec = decrypt_identity(priv_bytes, ct_hex)
        print(f"Decrypted: {dec}")
    except Exception as e:
        print(f"Exception: {e}")

test()

import os
import sys

# add backend path so imports work
sys.path.append(os.path.abspath('backend'))

from config import get_settings
from ecies_service import get_identity_blob, decrypt_identity

def test_nullifier(nullifier_hex):
    # Get active private key from environment / config
    settings = get_settings()
    priv_hex = settings.issuer_private_key_hex
    
    if not priv_hex:
        print("Error: No ISSUER_PRIVATE_KEY_HEX set in backend config/env.")
        return
        
    priv_bytes = bytes.fromhex(priv_hex)
    
    # Check if we have an encrypted blob for this nullifier in memory
    blob_hex = get_identity_blob(nullifier_hex)
    
    if not blob_hex:
        print(f"Error: No in-memory encrypted blob found for nullifier '{nullifier_hex}'.")
        print("Note: The backend must have captured the registration DURING THIS RUN to have the blob, as it is strictly stored in-memory and lost on restart.")
        return
        
    print(f"Found encrypted blob! Size: {len(blob_hex) // 2} bytes")
    
    # Try decrypt
    try:
        dec = decrypt_identity(priv_bytes, blob_hex)
        print(f"\nSUCCESS! Decrypted payload:\n{dec}")
    except Exception as e:
        print(f"\nFAILED! Exception during decryption: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_nullifier(sys.argv[1])
    else:
        print("Provide nullifier hex as argument.")

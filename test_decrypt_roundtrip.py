import sys
sys.path.append('backend')
from ecies_service import ecies_encrypt, ecies_decrypt
from ecdsa import SigningKey, SECP256k1

def test_roundtrip():
    # 1. Generate Issuer keys
    sk = SigningKey.generate(curve=SECP256k1)
    priv_hex = sk.to_string().hex()
    
    # Uncompressed public key format expected by standard libraries
    vk = sk.get_verifying_key()
    pub_hex = '04' + vk.pubkey.point.x().to_bytes(32, 'big').hex() + vk.pubkey.point.y().to_bytes(32, 'big').hex()
    
    # 2. Encrypt
    plaintext = b'test payload'
    ciphertext = ecies_encrypt(pub_hex, plaintext)
    
    print("Ciphertext len:", len(ciphertext))
    
    # 3. Decrypt
    decrypted = ecies_decrypt(bytes.fromhex(priv_hex), ciphertext)
    print("Decrypted:", decrypted.decode())

if __name__ == '__main__':
    test_roundtrip()

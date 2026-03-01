"""
Custom ECIES routines to precisely mirror eciesjs (used in the frontend).
Differences from standard cryptography ECIES:
1) HKDF input is `ephemeral_pub_key (65B) + shared_point (65B)`
2) HKDF info is empty (b"")
3) AES-GCM uses a 16-byte nonce
4) The stored payload format is: `ephemeral_pub(65) + nonce(16) + MAC(16) + ciphertext`
"""
import os
import json
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

def ecies_decrypt_compat(privkey_bytes: bytes, ciphertext: bytes) -> bytes:
    # 1. Parse eciesjs wire format
    # format = ephemeral_pub(65) || nonce(16) || MAC_tag(16) || ciphertext(n)
    eph_pub_bytes = ciphertext[:65]
    nonce         = ciphertext[65:81]
    mac_tag       = ciphertext[81:97]
    ct            = ciphertext[97:]
    
    # 2. Reconstruct standard AES-GCM payload expected by python (nonce, ct + MAC_tag)
    ct_and_tag = ct + mac_tag
    
    # 3. ECDH: Multiply ephemeral pub * our private key to get uncompressed shared point
    sk = SigningKey.from_string(privkey_bytes, curve=SECP256k1)
    vk = VerifyingKey.from_string(eph_pub_bytes[1:], curve=SECP256k1)  # strip 04 prefix
    
    # Point math: vk.pubkey.point * private_key
    shared_point = vk.pubkey.point * sk.privkey.secret_multiplier
    x_bytes = shared_point.x().to_bytes(32, 'big')
    y_bytes = shared_point.y().to_bytes(32, 'big')
    shared_point_bytes = b'\x04' + x_bytes + y_bytes
    
    # 4. HKDF to derive AES key
    # eciesjs hashes: senderPoint || sharedPoint
    hkdf_input = eph_pub_bytes + shared_point_bytes
    
    aes_key = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=b"",  # eciesjs uses empty info
        backend=default_backend(),
    ).derive(hkdf_input)
    
    # 5. Decrypt
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ct_and_tag, None)

# Quick test against the payload we know Failed
if __name__ == "__main__":
    priv_hex = '698eb1fac82f6ba130756ae59867c6a043032b937f73ded2471d278c962cae4d'
    # Test vector from JS test
    pub = '04fba314bf9c206288e1d8d54bc0c21aa4d5cda72eb77647febd65e12e9235536daa655ead1a399d7bdb3f76bad55450e7b76192cf3ee99bcfbd275004a9004416'
    # ciphertext from JS:
    ct_hex = "04808d71850fc82ca93ebd4d419f9d2d6d10c2fce98f2ff1c7ebd819c81b7eb3107bd48eb2f53d118c7ea8011da76fcd43e4efcac9ceb8a547a05711057c4d2e7d8d31ca608e37a198ed18f67d5dccab90a35172dfce73da3a3e0ce575dd4509dd00c98c59ea"
    
    plain = ecies_decrypt_compat(bytes.fromhex(priv_hex), bytes.fromhex(ct_hex))
    print(plain.decode())

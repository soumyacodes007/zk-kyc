import os
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

priv = bytes.fromhex("f1d984693bbe1b37d0a6f8a353730201f81aef91e91d3d0259ba00c135f481f4")
ct_hex = "049f4cd0504a59a6d7dc11bb5fe8e42a37f2510b319fcc45990987eda2346aaa6bd516cdb086709787455f2e168771aa14cd9557a038f82d8ba8e49a97d9219d5e2aed265d25f97e8490e89bc508ad3164ce50c2e025f59c42038e593f3e2e6a567075aadfe841a08f6454ddfb"

ciphertext = bytes.fromhex(ct_hex)

eph_pub_bytes = ciphertext[:65]
iv            = ciphertext[65:81]
tag           = ciphertext[81:97]
ct            = ciphertext[97:]

print("IV ", iv.hex())
print("Tag", tag.hex())
print("CT ", ct.hex())

sk = SigningKey.from_string(priv, curve=SECP256k1)
vk = VerifyingKey.from_string(eph_pub_bytes[1:], curve=SECP256k1)

shared_point = vk.pubkey.point * sk.privkey.secret_multiplier
shared_point_bytes = b'\x04' + shared_point.x().to_bytes(32, 'big') + shared_point.y().to_bytes(32, 'big')

hkdf_input = eph_pub_bytes + shared_point_bytes
aes_key = HKDF(
    algorithm=SHA256(), length=32, salt=None, info=b"", backend=default_backend()
).derive(hkdf_input)

print("Key", aes_key.hex())

aesgcm = AESGCM(aes_key)
# Encrypt "test payload" using the exact same IV to see what cryptography outputs
enc = aesgcm.encrypt(iv, b"test payload", None)
print("PyEnc", enc.hex())

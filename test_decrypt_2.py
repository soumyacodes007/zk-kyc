import sys
sys.path.append('backend')
from ecies_service import ecies_decrypt

def test_decrypt():
    priv = "f1d984693bbe1b37d0a6f8a353730201f81aef91e91d3d0259ba00c135f481f4"
    ct_hex = "04978597431be83f1cae89c15c56c8aba1e83ed8e97a4b3a648eb2dc5f3d5a2d4dbb3612e5ee99bd0aef3ac259f69a53d2bbd59485641913e6a1471a8975b049b06f5f3b0c96360e2bcbd17770d1dc46ea875d7183342e76b12c3e79b8cc8c8d63816b336c9ef635b350a99c15cfb8"
    
    try:
        dec = ecies_decrypt(bytes.fromhex(priv), bytes.fromhex(ct_hex))
        print("Success!", dec.decode())
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_decrypt()

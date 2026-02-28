from config import get_settings
s = get_settings()
print(f"NullifierRegistry: {s.nullifier_registry_id}")
print(f"SMTRegistry: {s.smt_registry_id}")
print(f"Deployer first 20: {s.deployer_mnemonic[:20]}...")
print(f"VK path: {s.verification_key_path}")
print("Config loaded OK!")

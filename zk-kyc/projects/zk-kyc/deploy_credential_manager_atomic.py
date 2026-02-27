"""
Deploy CredentialManager using atomic transaction group with proper fee coverage.
This is the CORRECT approach per AlgoKit best practices.
"""
import os
from pathlib import Path
from algosdk import mnemonic
from algosdk.v2client import algod
from algosdk.transaction import (
    ApplicationCreateTxn,
    OnComplete,
    StateSchema,
    wait_for_confirmation,
)
from algosdk.abi import Contract
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
    AccountTransactionSigner,
)
from dotenv import load_dotenv
import json

# Load environment
load_dotenv()

# Connect to testnet
algod_token = os.getenv("ALGOD_TOKEN", "")
algod_server = os.getenv("ALGOD_SERVER")
algod_client = algod.AlgodClient(algod_token, algod_server)

# Get deployer account
deployer_mnemonic = os.getenv("DEPLOYER_MNEMONIC")
deployer_key = mnemonic.to_private_key(deployer_mnemonic)
from algosdk.account import address_from_private_key
deployer_addr = address_from_private_key(deployer_key)

print(f"Deployer: {deployer_addr}")
print(f"Balance: {algod_client.account_info(deployer_addr)['amount'] / 1_000_000} ALGO")

# Load app spec
spec_path = Path(__file__).parent / "smart_contracts/artifacts/credential_manager/CredentialManager.arc56.json"
with open(spec_path) as f:
    app_spec = json.load(f)

# Extract TEAL programs (they're base64 encoded in ARC-56)
import base64
approval_program = base64.b64decode(app_spec["source"]["approval"])
clear_program = base64.b64decode(app_spec["source"]["clear"])

# Get state schema from ARC-56 format
global_schema = StateSchema(
    num_uints=app_spec["state"]["schema"]["global"]["ints"],
    num_byte_slices=app_spec["state"]["schema"]["global"]["bytes"],
)
local_schema = StateSchema(
    num_uints=app_spec["state"]["schema"]["local"]["ints"],
    num_byte_slices=app_spec["state"]["schema"]["local"]["bytes"],
)

# Create ABI contract from ARC-56 spec
# ARC-56 has methods at top level, need to convert to ARC-4 format
arc4_contract = {
    "name": app_spec["name"],
    "methods": app_spec["methods"],
    "networks": {}
}
contract = Contract.from_json(json.dumps(arc4_contract))
create_method = contract.get_method_by_name("create")

# Build atomic transaction composer
atc = AtomicTransactionComposer()
signer = AccountTransactionSigner(deployer_key)

# Get suggested params
sp = algod_client.suggested_params()

# CRITICAL: Set fee high enough to cover inner transaction (ASA creation = 1000 microALGO)
# Total needed: base fee (1000) + inner txn fee (1000) = 2000 microALGO minimum
sp.fee = 3000  # Extra buffer for safety
sp.flat_fee = True

# Add app create with ABI method call
atc.add_method_call(
    app_id=0,  # 0 = create new app
    method=create_method,
    sender=deployer_addr,
    sp=sp,
    signer=signer,
    approval_program=approval_program,
    clear_program=clear_program,
    global_schema=global_schema,
    local_schema=local_schema,
    extra_pages=3,  # Allow up to 8KB total (1 base page + 3 extra = 4 pages × 2KB)
    on_complete=OnComplete.NoOpOC,
)

print("\nSubmitting atomic transaction group...")
print("This will:")
print("  1. Create the CredentialManager app")
print("  2. Call the create() method which creates the KYC credential ASA")
print("  3. Fee pooling covers the inner ASA creation transaction")

try:
    result = atc.execute(algod_client, 4)
    
    app_id = result.abi_results[0].tx_info["application-index"]
    asa_id = result.abi_results[0].return_value
    
    print(f"\n✅ SUCCESS!")
    print(f"App ID: {app_id}")
    print(f"Credential ASA ID: {asa_id}")
    print(f"Explorer: https://testnet.algoexplorer.io/application/{app_id}")
    
    # Update deployed_contracts.json
    deployed_path = Path(__file__).parent / "deployed_contracts.json"
    with open(deployed_path) as f:
        deployed = json.load(f)
    
    # Get app address
    app_info = algod_client.application_info(app_id)
    app_address = app_info["params"]["creator"]  # This is wrong, need to derive it
    from algosdk.logic import get_application_address
    app_address = get_application_address(app_id)
    
    deployed["credential_manager"] = {
        "app_id": app_id,
        "app_address": app_address,
        "credential_asa_id": asa_id,
        "explorer": f"https://testnet.algoexplorer.io/application/{app_id}",
    }
    
    with open(deployed_path, "w") as f:
        json.dump(deployed, f, indent=2)
    
    print(f"\nUpdated deployed_contracts.json")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    raise

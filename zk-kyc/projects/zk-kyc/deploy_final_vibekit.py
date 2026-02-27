#!/usr/bin/env python3
"""
Deploy CredentialManager using direct algosdk with proper atomic group
"""
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from algosdk.abi import Contract
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
    AccountTransactionSigner
)

load_dotenv()


def main():
    print("=== Deploy CredentialManager (Atomic Group) ===\n")
    
    # Setup
    server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    token = os.environ.get("ALGOD_TOKEN", "")
    client = algod.AlgodClient(token, server)
    
    deployer_key = mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])
    deployer_addr = account.address_from_private_key(deployer_key)
    signer = AccountTransactionSigner(deployer_key)
    
    print(f"Deployer: {deployer_addr}")
    info = client.account_info(deployer_addr)
    print(f"Balance: {info['amount'] / 1_000_000:.4f} ALGO\n")
    
    # Load artifacts
    artifacts_dir = Path("smart_contracts/credential_manager/smart_contracts/artifacts/credential_manager")
    if not artifacts_dir.exists():
        artifacts_dir = Path("smart_contracts/artifacts/credential_manager")
    
    approval_teal = (artifacts_dir / "CredentialManager.approval.teal").read_text()
    clear_teal = (artifacts_dir / "CredentialManager.clear.teal").read_text()
    arc56 = json.loads((artifacts_dir / "CredentialManager.arc56.json").read_text())
    
    # Compile
    approval_result = client.compile(approval_teal)
    clear_result = client.compile(clear_teal)
    approval_prog = base64.b64decode(approval_result["result"])
    clear_prog = base64.b64decode(clear_result["result"])
    
    # Get create method
    contract_obj = Contract.from_json(json.dumps(arc56))
    create_method = contract_obj.get_method_by_name("create")
    
    print("Creating app with create() method call...\n")
    
    # Use AtomicTransactionComposer with method call during creation
    atc = AtomicTransactionComposer()
    sp = client.suggested_params()
    sp.fee = 3000  # Base + inner ASA creation
    sp.flat_fee = True
    
    # Add method call for creation (app_id=0 means create)
    atc.add_method_call(
        app_id=0,  # 0 = create new app
        method=create_method,
        sender=deployer_addr,
        sp=sp,
        signer=signer,
        approval_program=approval_prog,
        clear_program=clear_prog,
        global_schema=transaction.StateSchema(3, 1),
        local_schema=transaction.StateSchema(0, 0),
        method_args=[],
    )
    
    print("Step 1: Creating app and calling create() method...")
    result = atc.execute(client, 4)
    
    # Get app ID from ABI result
    app_id = result.abi_results[0].tx_info["application-index"]
    app_addr = transaction.logic.get_application_address(app_id)
    
    print(f"  App created: {app_id}")
    print(f"  App address: {app_addr}")
    print(f"  Create method executed successfully")
    
    # Get credential ASA ID
    app_info = client.application_info(app_id)
    global_state = app_info.get("params", {}).get("global-state", [])
    
    asa_id = None
    for item in global_state:
        key = base64.b64decode(item["key"]).decode()
        if key == "credential_asa_id":
            asa_id = item["value"]["uint"]
            break
    
    print(f"\n✅ CredentialManager fully deployed!")
    print(f"  App ID: {app_id}")
    print(f"  App Address: {app_addr}")
    print(f"  Credential ASA ID: {asa_id}")
    print(f"  https://testnet.algoexplorer.io/application/{app_id}")
    
    # Save
    deployed = {
        "network": "testnet",
        "deployer": deployer_addr,
        "nullifier_registry": {"app_id": 756272073},
        "smt_registry": {"app_id": 756272075},
        "kyc_box_storage": {"app_id": 756272299},
        "credential_manager": {
            "app_id": app_id,
            "app_address": app_addr,
            "credential_asa_id": asa_id
        }
    }
    
    output = Path("deployed_contracts.json")
    output.write_text(json.dumps(deployed, indent=2))
    
    print("\n" + "="*70)
    print("ALL ALGOKYC CONTRACTS DEPLOYED ✅")
    print("="*70)
    for name, info in deployed.items():
        if isinstance(info, dict) and "app_id" in info:
            print(f"  {name:25s} {info['app_id']}")
    print("="*70)
    print(f"\nSaved to: {output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Deploy CredentialManager using AlgoKit utils with proper funding
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from algosdk import mnemonic
import algokit_utils
from algokit_utils.models import app_spec

load_dotenv()

def main():
    print("=== Deploy CredentialManager with AlgoKit ===\n")
    
    # Setup AlgorandClient
    algorand = algokit_utils.AlgorandClient.from_environment()
    
    # Get deployer account
    deployer_mnemonic = os.environ["DEPLOYER_MNEMONIC"]
    deployer_key = mnemonic.to_private_key(deployer_mnemonic)
    deployer = algokit_utils.Account(private_key=deployer_key)
    
    print(f"Deployer: {deployer.address}")
    info = algorand.client.algod.account_info(deployer.address)
    print(f"Balance: {info['amount'] / 1_000_000:.4f} ALGO\n")
    
    # Load app spec
    artifacts_dir = Path("smart_contracts/credential_manager/smart_contracts/artifacts/credential_manager")
    if not artifacts_dir.exists():
        artifacts_dir = Path("smart_contracts/artifacts/credential_manager")
    
    arc56_path = artifacts_dir / "CredentialManager.arc56.json"
    arc56_json = json.loads(arc56_path.read_text())
    app_spec_obj = app_spec.AppSpec.from_json(arc56_json)
    
    # Get typed app factory
    factory = algorand.client.get_typed_app_factory(
        app_spec=app_spec_obj,
        default_sender=deployer.address,
        default_signer=deployer.signer
    )
    
    print("Deploying CredentialManager...")
    
    # Deploy with proper settings
    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        create_args=algokit_utils.DeployCreateArgs(),
    )
    
    print(f"  Operation: {result.operation_performed}")
    print(f"  App ID: {app_client.app_id}")
    print(f"  App Address: {app_client.app_address}")
    
    # Fund the app if it was just created
    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        print("\n  Funding app for ASA creation...")
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount.from_algo(0.5),
                sender=deployer.address,
                receiver=app_client.app_address,
                signer=deployer.signer,
            )
        )
        print("  Funded with 0.5 ALGO")
    
    print(f"\n✅ CredentialManager deployed!")
    print(f"  https://testnet.algoexplorer.io/application/{app_client.app_id}")
    
    # Get credential ASA ID from global state
    app_info = algorand.client.algod.application_info(app_client.app_id)
    global_state = app_info.get("params", {}).get("global-state", [])
    
    import base64
    asa_id = None
    for item in global_state:
        key = base64.b64decode(item["key"]).decode()
        if key == "credential_asa_id":
            asa_id = item["value"]["uint"]
            break
    
    if asa_id:
        print(f"  Credential ASA ID: {asa_id}")
    
    # Update deployed contracts JSON
    deployed = {
        "network": "testnet",
        "deployer": deployer.address,
        "nullifier_registry": {"app_id": 756272073},
        "smt_registry": {"app_id": 756272075},
        "kyc_box_storage": {"app_id": 756272299},
        "credential_manager": {
            "app_id": app_client.app_id,
            "app_address": app_client.app_address,
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

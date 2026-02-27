#!/usr/bin/env python3
"""
Final CredentialManager deployment - fund deployer, then create with proper fee
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

ARTIFACTS = Path(__file__).parent / "smart_contracts" / "artifacts"


def get_client():
    server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    token = os.environ.get("ALGOD_TOKEN", "")
    return algod.AlgodClient(token, server)


def wait_for_confirmation(client, txid, timeout=10):
    last_round = client.status()["last-round"]
    for _ in range(timeout):
        pending = client.pending_transaction_info(txid)
        if pending.get("confirmed-round", 0) > 0:
            return pending
        client.status_after_block(last_round + 1)
        last_round += 1
    raise TimeoutError(f"Transaction {txid} not confirmed")


def compile_teal(client, teal_source):
    result = client.compile(teal_source)
    return base64.b64decode(result["result"])


def main():
    print("=== Final CredentialManager Deployment ===\n")
    
    client = get_client()
    deployer_key = mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])
    deployer_addr = account.address_from_private_key(deployer_key)
    signer = AccountTransactionSigner(deployer_key)
    
    print(f"Deployer: {deployer_addr}")
    info = client.account_info(deployer_addr)
    print(f"Balance: {info['amount'] / 1_000_000:.4f} ALGO\n")
    
    # Copy artifacts
    nested_path = Path("smart_contracts/credential_manager/smart_contracts/artifacts/credential_manager")
    dest = ARTIFACTS / "credential_manager"
    
    if nested_path.exists():
        print("Copying artifacts...")
        import shutil
        dest.mkdir(exist_ok=True)
        for file in nested_path.glob("*"):
            shutil.copy(file, dest)
    
    # Read files
    approval_teal = (dest / "CredentialManager.approval.teal").read_text()
    clear_teal = (dest / "CredentialManager.clear.teal").read_text()
    arc56 = json.loads((dest / "CredentialManager.arc56.json").read_text())
    
    # Compile
    approval_prog = compile_teal(client, approval_teal)
    clear_prog = compile_teal(client, clear_teal)
    
    # Get method
    contract_obj = Contract.from_json(json.dumps(arc56))
    create_method = contract_obj.get_method_by_name("create")
    
    # Use AtomicTransactionComposer for proper ABI handling
    atc = AtomicTransactionComposer()
    
    sp = client.suggested_params()
    sp.fee = 3000  # Extra fee for inner ASA creation
    sp.flat_fee = True
    
    print("Creating app with ABI method...")
    
    # Add create transaction
    atc.add_method_call(
        app_id=0,  # 0 = create
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
    
    # Execute
    result = atc.execute(client, 4)
    app_id = result.abi_results[0].tx_info["application-index"]
    app_addr = transaction.logic.get_application_address(app_id)
    
    print(f"\n✅ CredentialManager deployed!")
    print(f"  App ID: {app_id}")
    print(f"  Address: {app_addr}")
    print(f"  https://testnet.algoexplorer.io/application/{app_id}")
    
    # Get the created ASA ID from global state
    app_info = client.application_info(app_id)
    global_state = app_info.get("params", {}).get("global-state", [])
    asa_id = None
    for item in global_state:
        key = base64.b64decode(item["key"]).decode()
        if key == "credential_asa_id":
            asa_id = item["value"]["uint"]
            break
    
    if asa_id:
        print(f"  Credential ASA ID: {asa_id}")
    
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

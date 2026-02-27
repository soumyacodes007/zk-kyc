#!/usr/bin/env python3
"""
Simple deployment using algosdk directly
"""
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from algosdk.abi import Contract

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


def deploy_contract(client, sender_key, contract_name, create_args=None):
    """Deploy a contract using its artifacts"""
    sender = account.address_from_private_key(sender_key)
    
    # Read TEAL files
    contract_dir = ARTIFACTS / contract_name
    approval_teal = (contract_dir / f"{contract_name.replace('_', ' ').title().replace(' ', '')}.approval.teal").read_text()
    clear_teal = (contract_dir / f"{contract_name.replace('_', ' ').title().replace(' ', '')}.clear.teal").read_text()
    
    # Read ARC56 spec for ABI
    arc56_path = contract_dir / f"{contract_name.replace('_', ' ').title().replace(' ', '')}.arc56.json"
    arc56 = json.loads(arc56_path.read_text())
    
    # Compile programs
    approval_prog = compile_teal(client, approval_teal)
    clear_prog = compile_teal(client, clear_teal)
    
    # Get suggested params
    sp = client.suggested_params()
    
    # Find create method
    create_method = next((m for m in arc56["methods"] if "create" in m.get("actions", {})), None)
    
    # Encode ABI method call
    app_args = []
    if create_method:
        contract_obj = Contract.from_json(json.dumps(arc56))
        method = contract_obj.get_method_by_name("create")
        
        if create_args:
            # Encode with args
            from algosdk.abi import ABIType
            encoded_args = [method.get_selector()]
            for arg, arg_spec in zip(create_args, method.args):
                arg_type = ABIType.from_string(str(arg_spec.type))
                encoded_args.append(arg_type.encode(arg))
            app_args = encoded_args
        else:
            # Just selector
            app_args = [method.get_selector()]
    
    # Determine state schema from arc56
    global_ints = global_bytes = local_ints = local_bytes = 0
    if "state" in arc56:
        state = arc56["state"]
        if "schema" in state:
            schema = state["schema"]
            global_ints = schema.get("global", {}).get("ints", 0)
            global_bytes = schema.get("global", {}).get("bytes", 0)
            local_ints = schema.get("local", {}).get("ints", 0)
            local_bytes = schema.get("local", {}).get("bytes", 0)
    
    # Create transaction
    txn = transaction.ApplicationCreateTxn(
        sender=sender,
        sp=sp,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_prog,
        clear_program=clear_prog,
        global_schema=transaction.StateSchema(global_ints, global_bytes),
        local_schema=transaction.StateSchema(local_ints, local_bytes),
        app_args=app_args,
    )
    
    # Sign and send
    signed = txn.sign(sender_key)
    txid = client.send_transaction(signed)
    print(f"  Txn: {txid}")
    
    # Wait for confirmation
    result = wait_for_confirmation(client, txid)
    app_id = result["application-index"]
    app_addr = transaction.logic.get_application_address(app_id)
    
    # Fund the app
    pay_txn = transaction.PaymentTxn(
        sender=sender,
        sp=sp,
        receiver=app_addr,
        amt=500_000,  # 0.5 ALGO
    )
    signed_pay = pay_txn.sign(sender_key)
    pay_txid = client.send_transaction(signed_pay)
    wait_for_confirmation(client, pay_txid)
    
    print(f"  ✅ App ID: {app_id}")
    print(f"  Address: {app_addr}")
    print(f"  https://testnet.algoexplorer.io/application/{app_id}\n")
    
    return {"app_id": app_id, "app_address": app_addr}


def main():
    print("=== AlgoKYC Testnet Deployment ===\n")
    
    client = get_client()
    deployer_key = mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])
    deployer_addr = account.address_from_private_key(deployer_key)
    
    print(f"Deployer: {deployer_addr}")
    info = client.account_info(deployer_addr)
    print(f"Balance: {info['amount'] / 1_000_000:.4f} ALGO\n")
    
    deployed = {}
    
    # 1. NullifierRegistry
    print("[1/4] NullifierRegistry")
    deployed["nullifier_registry"] = deploy_contract(client, deployer_key, "nullifier_registry")
    
    # 2. SMTRegistry (needs initial_root)
    print("[2/4] SMTRegistry")
    empty_root = b'\x00' * 32
    deployed["smt_registry"] = deploy_contract(client, deployer_key, "smt_registry", [empty_root])
    
    # 3. KYCBoxStorage
    print("[3/4] KYCBoxStorage")
    deployed["kyc_box_storage"] = deploy_contract(client, deployer_key, "kyc_box_storage")
    
    # 4. CredentialManager
    print("[4/4] CredentialManager")
    deployed["credential_manager"] = deploy_contract(client, deployer_key, "credential_manager")
    
    # Save
    output = Path("deployed_contracts.json")
    output.write_text(json.dumps(deployed, indent=2))
    
    print("\n" + "="*70)
    print("DEPLOYED CONTRACTS")
    print("="*70)
    for name, info in deployed.items():
        print(f"  {name:25s} {info['app_id']}")
    print("="*70)
    print(f"\nSaved to: {output}")


if __name__ == "__main__":
    main()

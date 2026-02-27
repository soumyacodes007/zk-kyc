#!/usr/bin/env python3
"""
deploy_contracts.py — Deploy AlgoKYC contracts to Algorand Testnet
Uses app spec files for proper ABI method encoding
"""
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.v2client import algod
from algosdk.atomic_transaction_composer import AccountTransactionSigner
from algokit_utils import ApplicationClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s: %(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS = Path(__file__).parent / "smart_contracts" / "artifacts"
DEPLOYED_JSON = Path(__file__).parent / "deployed_contracts.json"


def deploy_all():
    logger.info("=== AlgoKYC Testnet Deployment ===")
    
    # Get deployer account
    deployer_mnemonic = os.environ["DEPLOYER_MNEMONIC"]
    deployer_key = mnemonic.to_private_key(deployer_mnemonic)
    deployer_addr = account.address_from_private_key(deployer_key)
    deployer_signer = AccountTransactionSigner(deployer_key)
    
    # Get algod client
    algod_server = os.environ.get("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
    algod_token = os.environ.get("ALGOD_TOKEN", "")
    client = algod.AlgodClient(algod_token, algod_server)
    
    logger.info(f"Deployer: {deployer_addr}")
    
    # Check balance
    info = client.account_info(deployer_addr)
    balance = info["amount"] / 1_000_000
    logger.info(f"Balance: {balance:.4f} ALGO")
    
    deployed = {"network": algod_server, "deployer": deployer_addr}
    
    # 1. Deploy NullifierRegistry
    logger.info("\n[1/4] Deploying NullifierRegistry...")
    try:
        app_spec_path = ARTIFACTS / "nullifier_registry" / "NullifierRegistry.arc56.json"
        app_spec = json.loads(app_spec_path.read_text())
        
        app_client = ApplicationClient(
            algod_client=client,
            app_spec=app_spec,
            signer=deployer_signer,
        )
        
        result = app_client.create()
        app_id = result.app_id
        app_addr = result.app_address
        
        logger.info(f"✅ NullifierRegistry deployed: {app_id}")
        logger.info(f"   Address: {app_addr}")
        logger.info(f"   https://testnet.algoexplorer.io/application/{app_id}")
        
        deployed["nullifier_registry"] = {"app_id": app_id, "app_address": app_addr}
    except Exception as e:
        logger.error(f"❌ NullifierRegistry failed: {e}")
        raise
    
    # 2. Deploy SMTRegistry (requires initial_root parameter)
    logger.info("\n[2/4] Deploying SMTRegistry...")
    try:
        app_spec_path = ARTIFACTS / "smt_registry" / "SMTRegistry.arc56.json"
        app_spec = json.loads(app_spec_path.read_text())
        
        app_client = ApplicationClient(
            algod_client=client,
            app_spec=app_spec,
            signer=deployer_signer,
        )
        
        # Empty SMT root = 32 zero bytes
        empty_root = b'\x00' * 32
        
        result = app_client.create(initial_root=empty_root)
        app_id = result.app_id
        app_addr = result.app_address
        
        logger.info(f"✅ SMTRegistry deployed: {app_id}")
        logger.info(f"   Address: {app_addr}")
        logger.info(f"   https://testnet.algoexplorer.io/application/{app_id}")
        
        deployed["smt_registry"] = {"app_id": app_id, "app_address": app_addr}
    except Exception as e:
        logger.error(f"❌ SMTRegistry failed: {e}")
        raise
    
    # 3. Deploy KYCBoxStorage
    logger.info("\n[3/4] Deploying KYCBoxStorage...")
    try:
        app_spec_path = ARTIFACTS / "kyc_box_storage" / "KYCBoxStorage.arc56.json"
        app_spec = json.loads(app_spec_path.read_text())
        
        app_client = ApplicationClient(
            algod_client=client,
            app_spec=app_spec,
            signer=deployer_signer,
        )
        
        result = app_client.create()
        app_id = result.app_id
        app_addr = result.app_address
        
        logger.info(f"✅ KYCBoxStorage deployed: {app_id}")
        logger.info(f"   Address: {app_addr}")
        logger.info(f"   https://testnet.algoexplorer.io/application/{app_id}")
        
        deployed["kyc_box_storage"] = {"app_id": app_id, "app_address": app_addr}
    except Exception as e:
        logger.error(f"❌ KYCBoxStorage failed: {e}")
        raise
    
    # 4. Deploy CredentialManager (returns ASA ID)
    logger.info("\n[4/4] Deploying CredentialManager...")
    try:
        # First check if artifacts exist in nested location
        nested_path = Path("smart_contracts/credential_manager/smart_contracts/artifacts/credential_manager")
        if nested_path.exists():
            app_spec_path = nested_path / "CredentialManager.arc56.json"
        else:
            app_spec_path = ARTIFACTS / "credential_manager" / "CredentialManager.arc56.json"
            
        app_spec = json.loads(app_spec_path.read_text())
        
        app_client = ApplicationClient(
            algod_client=client,
            app_spec=app_spec,
            signer=deployer_signer,
        )
        
        # Fund the app before calling create (needs ALGO for ASA creation)
        result = app_client.create()
        app_id = result.app_id
        app_addr = result.app_address
        
        logger.info(f"✅ CredentialManager deployed: {app_id}")
        logger.info(f"   Address: {app_addr}")
        logger.info(f"   https://testnet.algoexplorer.io/application/{app_id}")
        
        deployed["credential_manager"] = {"app_id": app_id, "app_address": app_addr}
    except Exception as e:
        logger.error(f"❌ CredentialManager failed: {e}")
        raise
    
    # Save deployment info
    DEPLOYED_JSON.write_text(json.dumps(deployed, indent=2))
    
    print("\n" + "="*70)
    print("ALGOKYC TESTNET — DEPLOYED CONTRACTS")
    print("="*70)
    for key, val in deployed.items():
        if isinstance(val, dict) and "app_id" in val:
            print(f"  {key:25s} {val['app_id']}")
    print("="*70)
    print(f"\nSaved to: {DEPLOYED_JSON}")
    
    return deployed


if __name__ == "__main__":
    deploy_all()

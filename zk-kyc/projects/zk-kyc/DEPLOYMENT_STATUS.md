# AlgoKYC Testnet Deployment Status

## ✅ Successfully Deployed (3/4)

| Contract | App ID | Explorer Link |
|----------|--------|---------------|
| **NullifierRegistry** | 756272073 | https://testnet.algoexplorer.io/application/756272073 |
| **SMTRegistry** | 756272075 | https://testnet.algoexplorer.io/application/756272075 |
| **KYCBoxStorage** | 756272299 | https://testnet.algoexplorer.io/application/756272299 |

## ⚠️ CredentialManager - Requires Special Deployment

The CredentialManager contract has a unique requirement: its `create()` method creates an ASA internally, which requires the app account to be funded BEFORE the create method executes.

### The Challenge

Standard deployment flow:
1. Create app → Get app ID → Get app address
2. Fund app address
3. Call create() method

But CredentialManager requires:
1. Create app AND call create() in same transaction (due to `create="require"`)
2. App must be funded BEFORE create() runs
3. Can't know app address before creation

### Solution Options

#### Option 1: Modify Contract (Recommended for Production)
Split the ASA creation into a separate `initialize()` method:

```python
@arc4.abimethod(create="require")
def create(self) -> None:
    """Initialize contract state only."""
    self.issuer = Txn.sender
    self.total_issued = UInt64(0)
    self.total_revoked = UInt64(0)
    # Don't create ASA here

@arc4.abimethod()
def initialize_asa(self) -> UInt64:
    """Create the credential ASA. Call after funding the app."""
    assert Txn.sender == self.issuer, "Only issuer"
    assert self.credential_asa_id == UInt64(0), "Already initialized"
    
    result = itxn.AssetConfig(
        total=1_000_000_000,
        decimals=0,
        default_frozen=True,
        # ... rest of ASA config
    ).submit()
    
    self.credential_asa_id = result.created_asset.id
    return result.created_asset.id
```

Then deploy:
```bash
algokit project deploy testnet
# Fund the app
# Call initialize_asa()
```

#### Option 2: Use Atomic Group with Rekey
Complex but possible - requires rekeying logic.

#### Option 3: Manual Deployment Script
The deployment scripts in this directory attempted this but hit the funding timing issue.

## Deployer Account

**Address**: `6AUBAIKBTNH5VEGMXRXLXQW5RRXFKQ3JAQ3YSNONY4Z2LIFO6HETGQ7DTM`  
**Current Balance**: ~5.48 ALGO  
**Mnemonic**: Stored in `.env` file

## Next Steps

1. **For hackathon demo**: The 3 deployed contracts are sufficient to demonstrate the core ZK-KYC architecture
2. **For production**: Modify CredentialManager as shown in Option 1 above
3. **Alternative**: Deploy CredentialManager to localnet for testing

## Files

- `deployed_contracts.json` - Deployment info for the 3 live contracts
- `deploy_*.py` - Various deployment attempts (educational reference)
- `.env` - Contains deployer mnemonic and network config


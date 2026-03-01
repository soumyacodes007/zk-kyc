# Custodian Wallet Setup

## Overview
The dashboard now uses Lute Wallet authentication instead of password-based login. Only authorized custodian wallets can access the dashboard.

## Setup Instructions

### 1. Configure Custodian Wallet Addresses

Edit `src/App.jsx` and update the `CUSTODIAN_WHITELIST` object with the actual wallet addresses of your 5 custodians:

```javascript
const CUSTODIAN_WHITELIST = {
  'ACTUAL_WALLET_ADDRESS_1': 1,
  'ACTUAL_WALLET_ADDRESS_2': 2,
  'ACTUAL_WALLET_ADDRESS_3': 3,
  'ACTUAL_WALLET_ADDRESS_4': 4,
  'ACTUAL_WALLET_ADDRESS_5': 5,
}
```

### 2. How Custodians Login

**Option 1: Lute Wallet (Recommended)**
1. Click "Connect Lute Wallet"
2. Lute extension/mobile app opens
3. Approve the connection
4. Dashboard automatically logs in if wallet is authorized

**Option 2: Manual Entry**
1. Click "Enter Wallet Address Manually"
2. Paste the Algorand wallet address
3. Click Login
4. Dashboard verifies against whitelist

### 3. Security Features

- **Whitelist Verification**: Only pre-authorized addresses can access
- **No Passwords**: Eliminates password-related vulnerabilities
- **Cryptographic Proof**: Wallet connection proves ownership
- **Testnet Only**: Currently configured for Algorand Testnet

### 4. Production Deployment

For production, move the whitelist to:
- Backend API endpoint: `GET /api/v1/custodians/verify/{address}`
- Environment variables
- Secure configuration management system

### 5. Testing

To test locally:
1. Use Lute Wallet on Testnet
2. Add your test wallet address to the whitelist
3. Connect and verify access

## Troubleshooting

**"This wallet is not authorized"**
- Verify the wallet address is in the whitelist
- Check for typos in the address
- Ensure you're on the correct network (Testnet)

**"Wallet connection failed"**
- Install Lute Wallet extension/app
- Ensure Lute is configured for Testnet
- Check browser console for detailed errors

**Connection cancelled**
- User closed the Lute popup
- Simply try connecting again

# AlgoKYC — Phase 1: ZK Circuits

## Overview

This directory contains the dual ZK circuit implementation for AlgoKYC.

| Toolchain | Purpose | Location |
|---|---|---|
| **gnark (Go)** | On-chain PLONK verifier via AlgoPlonk | `gnark/` |
| **Circom + snarkjs** | In-browser WASM proof generation | `circom/` |

Both circuits implement **identical logic** — same PLONK on BN254, same Poseidon hashing, same SMT depth 20.

---

## Circuit Logic (V1 — RSA deferred)

```
Private inputs:
  aadhaarHash, walletSecret, dobYear, currentYear,
  nationalityIN, kycStatus,
  merkleSiblings[20], merklePos[20]

Constraints:
  1. nullifier = Poseidon(aadhaarHash, appId, walletSecret)
  2. nullifier (public) == computed nullifier
  3. nationalityIN == 1  (Indian)
  4. isIndian (public)   == 1
  5. currentYear - dobYear >= 18
  6. isAdult (public)    == 1  
  7. kycStatus           == 1  (VERIFIED)
  8. isKYCVerified (public) == 1
  9. SMT inclusion proof: walk 20 levels, root matches on-chain SMTRegistry
```

---

## gnark Setup (requires Go)

### Install Go
Download from https://go.dev/dl/ and install.

### Run
```bash
cd gnark
go mod tidy
go run . setup     # compile circuit + generate proving/verifying keys
go run . prove     # generate test proof with mock inputs  
go run . verifier  # export AlgoPlonk PuyaPy LogicSig verifier → contracts/kyc_verifier/
```

### AlgoPlonk Output
After `go run . verifier`, the PuyaPy LogicSig verifier is written to:
```
../../zk-kyc/projects/zk-kyc/smart_contracts/kyc_verifier/contract.py
```
Then compile + deploy via AlgoKit:
```bash
cd ../../zk-kyc/projects/zk-kyc
algokit compile python smart_contracts/kyc_verifier/contract.py --out-dir smart_contracts/artifacts/kyc_verifier
```

---

## Circom + snarkjs Setup (requires Node.js + circom)

### Install circom
```bash
# Rust-based compiler
cargo install circom
```
Or download the binary from https://docs.circom.io/getting-started/installation/

### Run
```bash
cd circom
npm install                # install circomlib + snarkjs
node scripts/setup.js      # compile circuit + ptau download + zkey generation (~60s)
node scripts/prove.js      # generate test proof
node scripts/verify.js     # verify proof locally
npm test                   # run full circuit test suite
```

### Browser Integration
After setup, the browser SDK (Phase 3) uses:
- `build/kyc_js/kyc.wasm` — compiled circuit WASM
- `build/kyc_final.zkey` — proving key
- `snarkjs.plonk.fullProve()` — runs entirely in a Web Worker

---

## Public Inputs (On-Chain)

| Signal | Description |
|---|---|
| `nullifier` | Poseidon(aadhaarHash, appId, walletSecret) |
| `merkleRoot` | Current SMT root from `SMTRegistry` contract |
| `appId` | Requesting dApp's app ID (scope per-app) |
| `isIndian` | 1 = nationality confirmed Indian |
| `isAdult` | 1 = age ≥ 18 confirmed |
| `isKYCVerified` | 1 = UIDAI KYC status confirmed |

---

## V1.1 Roadmap (pre-mainnet)

- [ ] RSA-2048 UIDAI signature verification inside circuit (~15-25k extra constraints)
- [ ] Full DOB comparison (month + day, not just year)
- [ ] Optional field commitments for state, gender, exact age

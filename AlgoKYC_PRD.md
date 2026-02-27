# AlgoKYC SDK
### Zero-Knowledge KYC for Algorand
**Product Requirements Document v1.0**
AlgoBharat Hack Series 3.0 | RegTech Track

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [Full System Architecture](#4-full-system-architecture)
5. [Key Management & Conditional Accountability](#5-key-management--conditional-accountability)
6. [SDK — The 3-Line Integration](#6-sdk--the-3-line-integration)
7. [Custodian Dashboard](#7-custodian-dashboard)
8. [Credential Revocation — Sparse Merkle Tree](#8-credential-revocation--sparse-merkle-tree)
9. [Build Plan — Hackathon Timeline](#9-build-plan--hackathon-timeline)
10. [Security Model](#10-security-model)
11. [DPDP Act Compliance Mapping](#11-dpdp-act-compliance-mapping)

---

## 1. Executive Summary

AlgoKYC is an open-source SDK that brings Zero-Knowledge KYC verification to the Algorand blockchain. Any developer can add a fully DPDP-compliant KYC widget to their application in three lines of code — without ever storing, transmitting, or touching a user's personal data.

> **The Core Promise**
> A DeFi lending protocol, a crypto exchange, or any regulated Algorand app can gate access based on KYC status — without seeing a single byte of user identity data.
>
> User proves: *"I am a KYC-verified Indian adult"*
> App receives: `true / false`
> Data stored anywhere: **zero**

| Metric | Value |
|---|---|
| Target Ecosystem | Algorand Mainnet + Testnet |
| Primary Market | Indian fintech developers (DPDP Act compliance) |
| Proof System | PLONK (via AlgoPlonk) |
| Curve | BN254 |
| Browser Proof Time | 2–8 seconds (WASM) |
| Lines to Integrate | **3** |
| Prize Track | AlgoBharat Hack Series 3.0 — RegTech |

---

## 2. Problem Statement

### 2.1 The KYC Data Crisis

Every regulated app in India — exchanges, DeFi protocols, lending platforms — must verify user identity. The current approach is fundamentally broken:

- User uploads Aadhaar card, PAN, selfie to each app
- Each app stores this data on their own servers
- 50 apps = 50 copies of your most sensitive identity documents
- Each server is a breach waiting to happen — and breaches have happened repeatedly
- On-chain KYC is even worse: data becomes public and immutable forever

> **Root Cause**
> The system conflates two separate operations:
>
> `VERIFICATION` — confirming a fact about a person ("they are 18+")
> `DISCLOSURE`   — revealing the underlying data ("their DOB is 01/01/1995")
>
> Nobody needs the second. Everyone currently demands it anyway.

### 2.2 The DPDP Act Creates Legal Urgency

India's Digital Personal Data Protection Act (2023) introduces **data minimization** as a core legal principle: collect only what you need, retain only as long as necessary. The current KYC industry violates this principle structurally.

Every Indian fintech now faces a choice: rebuild KYC with privacy-by-design, or face regulatory action. AlgoKYC is the infrastructure that makes compliance technically achievable.

---

## 3. Solution Overview

### 3.1 What AlgoKYC Does

AlgoKYC uses Zero-Knowledge Proofs to separate verification from disclosure. The user proves a set of mandatory facts about themselves — without revealing the underlying documents — and receives a non-transferable on-chain credential. Any app checks the credential.

| Layer | What Happens |
|---|---|
| User Device | Aadhaar Offline XML parsed locally. ZK proof generated in browser. Raw data deleted after proof gen. Never leaves device. |
| ZK Proof | Cryptographic proof that user satisfies mandatory KYC requirements. ~200 bytes. Mathematically impossible to reverse. |
| Algorand Chain | LogicSig verifier validates proof. Nullifier anchored on-chain. Non-transferable credential ASA issued to wallet. |
| Encrypted Blob | Encrypted identity package stored in Algorand box storage. Only issuer's private key can decrypt. Accountability layer. |
| App Layer | SDK exposes single function: `verifyKYC(wallet)` → boolean. App never touched user data. |

### 3.2 Mandatory vs Optional Fields

Unlike BBS+ (where users can hide anything, breaking accountability), AlgoKYC uses an **issuer-enforced field policy**:

| Field | Type | App Receives | User Can Hide |
|---|---|---|---|
| Is Indian Citizen | MANDATORY | true/false | No |
| Is 18+ (Adult) | MANDATORY | true/false | No |
| KYC Verified | MANDATORY | true/false | No |
| Not Sanctioned | MANDATORY | true/false | No |
| Nullifier | MANDATORY | Public on-chain | No |
| State / City | OPTIONAL | Only if app requests | Yes |
| Gender | OPTIONAL | Only if app requests | Yes |
| Exact Age | OPTIONAL | Only if app requests | Yes |
| Name | OPTIONAL | Only if app requests | Yes |

> **Design Rationale**
> Mandatory fields enforce the minimum accountability floor required by law enforcement.
> Optional fields give users genuine DPDP data minimization rights.
> The issuer sets the floor. The user controls everything above the floor.

---

## 4. Full System Architecture

### 4.1 Cryptographic Stack

| Component | Choice & Rationale |
|---|---|
| Proof System | PLONK — no per-circuit trusted setup, reuses Aztec Ignition ceremony. Circuit updates don't require re-ceremony. |
| Elliptic Curve | BN254 — ~145,000 opcode budget on AVM vs ~185,000 for BLS12-381. Cheaper, faster, sufficient security for KYC. |
| Verifier Type | LogicSig — max budget 320,000 opcodes vs 190,400 for smart contracts. Preserves smart contract budget for app logic. |
| Nullifier Hash | Poseidon — ZK-friendly, dramatically fewer circuit constraints than SHA-256. |
| Merkle Tree Hash | MiMC — ZK-optimized, ideal for tree operations inside circuits. |
| Merkle Tree Type | Sparse Merkle Tree — O(1) leaf updates enable efficient credential revocation without tree rebuild. |
| Toolchain | AlgoPlonk (gnark) — auto-generates Algorand LogicSig verifier from circuit definition. |
| Smart Contracts | Python (PuyaPy via AlgoKit) — nullifier registry, credential ASA management, box storage, Sparse Merkle root. AlgoPlonk auto-generates the PuyaPy verifier. |
| Proof Generation | TypeScript + snarkjs WASM — runs entirely in browser. XML never leaves user's device. |
| SDK + Widget | TypeScript + React — `npm install algokyc-sdk`. 3-line developer integration. Submits proof to Algorand chain. |
| Python Backend | Python — on-chain verification queries, Shamir key management, issuer server, custodian dashboard API, court order flow. Zero user PII ever reaches this server. |
| Blob Encryption | Python (`eciespy`) — issuer public key encrypts identity blob on-chain. Only issuer private key decrypts. |
| Key Management | Python (`secretsharing`) — Shamir 5/3 split + HSM integration for production. |

### 4.2 Data Flow — Proof Generation

```
┌─────────────────────────────────────────────────────────┐
│                    USER'S BROWSER                        │
│                                                          │
│  Aadhaar Offline XML (user downloads from UIDAI)         │
│         │                                                │
│         ▼                                                │
│  XML Parser (local, in-memory)                           │
│         │                                                │
│    ┌────┴─────────────────────┐                          │
│    │                          │                          │
│    ▼                          ▼                          │
│  snarkjs WASM (local)     Encrypt(identity, issuerPubKey)│
│  → PLONK proof gen        → encrypted_blob               │
│  → ~200 byte proof            │                          │
│    │                          │                          │
│    ▼                          ▼                          │
│  nullifier = Poseidon(aadhaar_hash, app_id, wallet_secret)│
│                                                          │
│  RAW XML DELETED FROM MEMORY                             │
│  NOTHING SENSITIVE EVER LEFT THIS BROWSER TAB            │
└──────────────┬───────────────────────┬───────────────────┘
               │ proof + nullifier     │ encrypted_blob
               ▼                       ▼
        TypeScript SDK            Algorand Box Storage
        → Algorand chain          (nullifier → blob mapping)
        → LogicSig verifier
        → Credential ASA issued
               │
               ▼
        Python Backend
        (on-chain reads, Shamir,
         issuer ops, court orders)
        NEVER receives XML or PII
```

### 4.3 On-Chain Components

| Component | Description |
|---|---|
| LogicSig Verifier | Auto-generated by AlgoPlonk from gnark circuit. Validates PLONK proof on BN254 curve. ~145k opcode budget. |
| Nullifier Registry | Smart contract mapping: `nullifier_hash → wallet_address`. Prevents same Aadhaar from creating multiple credentials. One Aadhaar = one wallet. |
| Credential ASA | Non-transferable Algorand Standard Asset issued to verified wallet. Clawback enabled (for revocation). Metadata: verified=true, tier, expiry. |
| Box Storage | Algorand box storage per wallet: stores encrypted identity blob. Key = nullifier. Only readable by issuer private key. |
| Sparse Merkle Root | On-chain root of Sparse Merkle Tree of valid nullifiers. Apps verify inclusion proof to confirm credential is not revoked. |
| Issuer Public Key | Issuer's public key anchored on-chain. Any app or auditor can verify that a credential was issued by the legitimate issuer. |

### 4.4 ZK Circuit Design

The circuit is written in gnark (Go) and compiled to PLONK. AlgoPlonk auto-generates the Algorand LogicSig verifier.

```go
// Circuit: KYCProof (pseudocode, ~100k constraints estimated)

// Public inputs (revealed on-chain)
nullifier     = Poseidon(aadhaarHash, app_id, walletSecret)  // per-app nullifier
merkleRoot    = root of valid credentials tree
appId         = which app is requesting verification

// Private inputs (never leave device)
aadhaarHash      = hash of full Aadhaar number
walletSecret     = user's wallet-derived secret
dob              = date of birth from XML
nationality      = from XML
kycStatus        = from XML
aadhaar_xml_data = raw XML content (all fields)
uidai_signature  = RSA-2048 signature embedded in XML
merklePath[]     = Sparse Merkle inclusion path
optionalFields[] = state, gender, age (app-gated)

// Step 1: Verify UIDAI actually signed this XML
// UIDAI public key is hardcoded as a circuit constant — publicly known
assert RSA_verify(
  UIDAI_PUBLIC_KEY,    // hardcoded constant, not a user input
  aadhaar_xml_data,    // full XML content
  uidai_signature      // signature from the XML file
) == true              // fake XML = no valid signature = proof fails here

// Step 2: Mandatory claims (only reached if signature valid)
assert nationality == 'IN'
assert age(dob, currentDate) >= 18
assert kycStatus == VERIFIED
assert SMT.verify(nullifier, merkleRoot, merklePath)

// Step 3: Optional constraints (only active if app requests)
if (appRequires.state)    → reveal stateCommitment
if (appRequires.ageExact) → reveal ageCommitment
```

### 4.5 Per-App Nullifier Design

A global nullifier `Poseidon(aadhaarHash, walletSecret)` would create a **cross-app tracking identifier** — a chain observer could link the same person across every app they use, destroying privacy.

AlgoKYC uses per-app nullifiers by including `app_id` in the nullifier derivation:

```
nullifier = Poseidon(aadhaar_hash, app_id, wallet_secret)
```

| Scenario | Global Nullifier | Per-App Nullifier |
|---|---|---|
| Same user on App X | 0xABC123 | 0xABC123 |
| Same user on App Y | 0xABC123 ← linkable | 0xDEF456 ← unlinkable |
| Chain observer conclusion | "Same person uses both apps" | "Two different users" |
| Privacy guarantee | ❌ Broken | ✅ Preserved |

The `appId` was already a public input in the circuit. This is a one-line change in nullifier derivation with a massive privacy impact.

### 4.6 Aadhaar Signature Verification

Every Aadhaar Offline XML downloaded from UIDAI's portal is **digitally signed by UIDAI's RSA-2048 private key** at the moment of download. The signature is embedded directly in the XML file.

Without verifying this signature inside the circuit, anyone could craft a fake XML with arbitrary fields and generate a valid proof:

```xml
<!-- Attacker's fake XML — never touched UIDAI -->
<name>Satish Kumar</name>
<nationality>IN</nationality>
<kycStatus>VERIFIED</kycStatus>
<Signature>FAKEFAKE123...</Signature>
```

The circuit **must** verify the UIDAI signature as the first constraint. UIDAI's public key is publicly available and hardcoded as a circuit constant — it is not a user-supplied input and cannot be manipulated.

```
Genuine UIDAI XML:
  RSA_verify(UIDAI_PUBLIC_KEY, xml_data, uidai_signature) → TRUE
  → Proof generation continues

Fake / tampered XML:
  RSA_verify(UIDAI_PUBLIC_KEY, xml_data, fake_signature) → FALSE
  → Proof generation fails immediately. No credential issued.
```

> **Cost:** RSA-2048 verification adds ~15,000–25,000 constraints to the circuit, increasing estimated size from ~80k to ~100k constraints. This remains well within AlgoPlonk's supported range (up to 2^17 = 128k constraints) and is non-negotiable for production security.

---

## 5. Key Management & Conditional Accountability

### 5.1 The Accountability Problem

ZK-KYC cannot mean anonymous crime. Law enforcement requires a legally compliant path to reveal identity when a court order is issued. AlgoKYC implements **Conditional Anonymity**: private to everyone except authorized legal proceedings.

### 5.2 Encrypted Identity Blob

During proof generation, a separate encrypted package is created and stored in Algorand box storage:

```javascript
encrypted_blob = ECIES.encrypt(
  plaintext: {
    aadhaar_number: 'XXXX-XXXX-XXXX',
    name:           'User Full Name',
    dob:            '01/01/1995',
    address:        '...',
    phone:          '...',
    nullifier:      '0xABC123...'   // linking key
  },
  publicKey: issuer.publicKey       // only issuer can decrypt
)

// Stored in Algorand box storage:
// Key:   nullifier_hash
// Value: encrypted_blob
```

### 5.3 Shamir Secret Sharing — Issuer Key Protection

The issuer's master private key is never stored in one place. It is split into 5 shares using Shamir's Secret Sharing. Any **3 of 5** shares can reconstruct the key. No single entity can decrypt user data unilaterally.

```javascript
// Key generation and splitting
const issuerKeyPair = generateKeyPair()  // RSA-4096 or EC P-384

const shares = shamirSecretSharing.split(issuerKeyPair.privateKey, {
  shares: 5,
  threshold: 3
})

// Each share encrypted with that custodian's public key
encryptedShare[0] = encrypt(shares[0], custodian_UIDAI.publicKey)
encryptedShare[1] = encrypt(shares[1], custodian_MinFinance.publicKey)
encryptedShare[2] = encrypt(shares[2], custodian_KYCProvider.publicKey)
encryptedShare[3] = encrypt(shares[3], custodian_AlgoFoundation.publicKey)
encryptedShare[4] = encrypt(shares[4], custodian_Judiciary.publicKey)

// Court order decrypt flow
decryptedShare1 = custodian1.HSM.decrypt(encryptedShare[0])
decryptedShare2 = custodian2.HSM.decrypt(encryptedShare[1])
decryptedShare3 = custodian3.HSM.decrypt(encryptedShare[2])

issuerKey = shamirSecretSharing.combine([s1, s2, s3])  // 3/5 threshold met
identity  = ECIES.decrypt(encrypted_blob, issuerKey)   // identity revealed
```

| Custodian | Role |
|---|---|
| Custodian 1 — UIDAI Representative | Aadhaar authority — natural custodian for identity data |
| Custodian 2 — Ministry of Finance | Financial crime jurisdiction — required for AML cases |
| Custodian 3 — Licensed KYC Provider | Regulated KYC entity under RBI/SEBI framework |
| Custodian 4 — Algorand Foundation India | Protocol-level accountability |
| Custodian 5 — Judiciary-Appointed Custodian | Independent judicial oversight |

> **Production Key Storage**
> Each custodian's private key SHALL be stored in a FIPS 140-2 Level 3 certified HSM (e.g., Thales Luna, AWS CloudHSM, YubiHSM 2). Key operations occur exclusively within the HSM secure boundary. Private keys never enter system RAM. Every decryption operation produces a tamper-evident audit log entry.
>
> For hackathon demo: environment variable keypairs with documented production plan.

### 5.4 Court Order Flow

```
Crime detected → wallet 0xDEF789 flagged
        ↓
Government queries Algorand chain
        ↓
nullifier = 0xABC123 linked to wallet 0xDEF789
        ↓
Court order issued to issuer
        ↓
3 of 5 custodians verify court order legitimacy
        ↓
Each custodian decrypts their share from HSM
        ↓
Shamir reconstruction: issuer master key recovered
        ↓
encrypted_blob[0xABC123] decrypted
        ↓
Identity revealed: Name, Aadhaar, DOB, Address
        ↓
Audit log recorded on-chain + off-chain
        ↓
Issuer key wiped from memory. Re-split. New shares distributed.
```

---

## 6. SDK — The 3-Line Integration

### 6.1 Developer Experience Goal

The SDK must be so simple that a developer who has never heard of ZK proofs can add DPDP-compliant KYC to their Algorand app in under 5 minutes. All cryptographic complexity is hidden behind a single React widget and a single verification function.

### 6.2 Installation

```bash
npm install algokyc-sdk
```

### 6.3 The 3-Line Integration

```tsx
import { AlgoKYC } from 'algokyc-sdk'

<AlgoKYC appId="your_app_id" onVerified={(cred) => grantAccess(cred)} />

// That's it. Widget handles everything. Data never touched.
```

### 6.4 Server-Side Verification

```typescript
import { verifyKYC } from 'algokyc-sdk/server'

const result = await verifyKYC(walletAddress)
// returns: { verified: true, tier: 'full', expiresAt: Date }
// Internally calls Python backend → queries Algorand chain
```

> **Architecture Note:** Proof generation runs entirely in the user's browser via snarkjs WASM — XML never touches any server. The TypeScript SDK handles proof generation + Algorand chain submission. The Python backend handles everything else: on-chain verification queries, Shamir key operations, issuer logic, and custodian dashboard API. Python never receives user PII.

### 6.5 Full SDK API Reference

| Function / Component | Layer | Description |
|---|---|---|
| `<AlgoKYC />` | TypeScript | React widget. Handles full browser-side flow: Aadhaar XML upload, snarkjs WASM proof generation, chain submission. Props: `appId`, `onVerified`, `onError`, `theme`, `requiredFields[]`. |
| `verifyKYC(wallet)` | TypeScript → Python | SDK queries Python backend which reads Algorand chain. Returns status object. No PII involved. |
| `generateProof(xmlPath, walletSecret)` | TypeScript (browser WASM) | Runs entirely local. Parses XML, generates PLONK proof via snarkjs. Returns `{ proof, publicSignals, encryptedBlob }`. XML deleted after. |
| `submitCredential(proof, blob)` | TypeScript → Algorand | Submits proof to LogicSig verifier, stores encrypted blob in box storage. Returns `txId`. |
| `revokeCredential(nullifier)` | Python (issuer only) | Updates Sparse Merkle Tree. Credential immediately invalid on-chain. |
| `checkRevocation(nullifier)` | TypeScript → Python | Returns SMT inclusion/exclusion proof from chain. |

### 6.6 Widget UX Flow

```
Step 1  User clicks 'Verify KYC' in your app
        ↓
Step 2  AlgoKYC widget opens
        Embedded UIDAI webview shown
        "Download your Aadhaar XML — your data never leaves your device"
        ↓
Step 3  User completes OTP on UIDAI portal (widget never sees this)
        ZIP auto-detected from downloads
        ↓
Step 4  "Generating your privacy proof..." (2-8 seconds, WASM)
        Progress bar + "Your data is being processed locally 🔒"
        ↓
Step 5  Proof submitted to Algorand
        Credential ASA issued to wallet
        ↓
Step 6  Widget closes, onVerified() callback fires
        App grants access — never saw user data
```

---

## 7. Custodian Dashboard

### 7.1 Overview

A separate web interface for the 5 custodians managing Shamir shares. Custodians log in with their Algorand wallet and can view, approve, or reject court order decryption requests. The dashboard enforces the 3/5 threshold — decryption only proceeds when 3 custodians independently approve.

### 7.2 Dashboard Screens

**Screen 1 — Custodian Login**
```
┌────────────────────────────────────────┐
│  AlgoKYC Custodian Panel               │
│  Secure Access — Court Order Decryption│
├────────────────────────────────────────┤
│  Connect Wallet (Pera / Defly)         │
│  [Connect Wallet Button]               │
│                                        │
│  Role: UIDAI Representative            │
│  Share: #1 of 5                        │
│  Status: 🟢 Active                     │
└────────────────────────────────────────┘
```

**Screen 2 — Active Court Orders**
```
┌─────────────────────────────────────────────────┐
│  Pending Court Orders                    [1]    │
├─────────────────────────────────────────────────┤
│  Case #001                                      │
│  Wallet:    0xDEF789...                         │
│  Nullifier: 0xABC123...                         │
│  Reason:    Financial fraud - Cyber Cell Delhi  │
│  Filed by:  Commissioner of Police, Delhi       │
│  Filed on:  2025-04-01                          │
│  Order:     [View PDF]                          │
│                                                 │
│  Approvals: ██░░░░  1 / 3 required              │
│  Custodian 1 (UIDAI):   ✅ Approved             │
│  Custodian 2 (FinMin):  ⏳ Pending              │
│  Custodian 3 (KYC):     ⏳ Pending              │
│                                                 │
│  [ APPROVE THIS REQUEST ]  [ REJECT ]           │
└─────────────────────────────────────────────────┘
```

**Screen 3 — Live Decryption (3/5 Met)**
```
┌─────────────────────────────────────────────────┐
│  ✅ THRESHOLD MET — 3 / 5 Custodians Approved   │
│                                                 │
│  Reconstructing issuer key...                   │
│  ████████████████████████ 100%                  │
│                                                 │
│  Decrypting identity blob...                    │
│  ████████████████████████ 100%                  │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  IDENTITY REVEALED  (Court Order #001)  │   │
│  │  Name:    Satish Kumar                  │   │
│  │  Aadhaar: XXXX-XXXX-7432               │   │
│  │  DOB:     01/01/1995                    │   │
│  │  Address: Delhi, India                  │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  Audit log recorded on-chain ✅                 │
│  Issuer key wiped from memory ✅                │
└─────────────────────────────────────────────────┘
```

### 7.3 Security Requirements for Dashboard

- All custodian actions signed with their Algorand wallet — non-repudiable
- Approval transactions recorded on Algorand with timestamp
- Decrypted identity never persisted — displayed in memory only, session auto-expires
- Full audit trail exported to PDF for court records
- Rate limiting: max 1 decryption per case ID
- 2-of-2 confirmation required before displaying decrypted identity (confirm intent)

---

## 8. Credential Revocation — Sparse Merkle Tree

### 8.1 Why Sparse Merkle Tree

When a credential needs to be revoked (Aadhaar cancelled, fraud detected, credential expired), the on-chain registry must update efficiently. A regular Merkle tree requires a full rebuild on any update. A Sparse Merkle Tree allows **O(1) leaf updates** — a single leaf modification propagates up the tree in O(log n) operations without touching other leaves.

| Operation | Regular Merkle Tree | Sparse Merkle Tree |
|---|---|---|
| Add credential | O(log n) | O(log n) |
| Revoke credential | O(n) full rebuild | O(log n) single leaf update |
| Check valid | O(log n) | O(log n) |
| On-chain cost per revoke | High (full root change) | Low (single path update) |
| Algorand txns for revoke | Many | **1** |

### 8.2 Revocation Flow

```javascript
// Issuer revokes credential for nullifier 0xABC123

SMT.update(nullifier: '0xABC123', value: REVOKED)
// → new SMT root computed

updateMerkleRoot(newRoot)
// → 1 Algorand transaction

// All apps now: inclusion proof fails for 0xABC123
verifyKYC(wallet) // → { verified: false, reason: 'revoked' }

// Cost: 1 Algorand transaction. Immediate. No rebuild.
```

---

## 9. Development Tooling — VibeKit MCP

### 9.1 What is VibeKit

VibeKit is an Algorand-specific CLI that configures your AI coding agent (Claude Code / Cursor / VS Code) for Algorand development in one command. It installs Agent Skills for Algorand knowledge, MCP servers for documentation, and 44 blockchain MCP tools that let the AI interact directly with the chain.

```bash
npx @algorandfoundation/algokit-vibekit@latest init
```

Done. Your AI assistant now has full Algorand context and can deploy contracts, query state, and test on LocalNet — all inside a single conversation.

### 9.2 The 44 MCP Tools

| Category | Tools |
|---|---|
| Contracts (7) | Deploy, call, ABI introspect, dry-run |
| Assets (8) | Create ASA, transfer, freeze, clawback |
| Accounts (7) | Fund, switch, send, balance check |
| State (3) | Global state, local state, box storage |
| Indexer (5) | Transaction search, logs query, account history |

Box storage queries are directly relevant — AlgoKYC stores encrypted blobs in Algorand box storage. VibeKit can read and debug these in real time during development.

### 9.3 Key Security Design — Aligned With AlgoKYC

VibeKit implements private key isolation as a core design constraint — the AI agent requests transactions, a separate wallet provider signs them. Keys never enter the LLM context. HashiCorp Vault or OS keyring can be used as the signing backend.

This is the same principle AlgoKYC enforces: the SDK never sees user keys, the custodian dashboard never exposes issuer keys to the application layer. VibeKit's architecture validates this design choice at the tooling level.

### 9.4 How It Fits The Build Plan

```
LocalNet setup          → vibekit handles automatically
Contract deployment     → AI deploys LogicSig verifier via MCP
Box storage testing     → AI queries encrypted blobs directly
Testnet migration       → single MCP command
Nullifier registry test → AI calls contract, checks state, debugs
```

> **Note:** VibeKit accelerates iteration but does not replace architectural judgement. The AI is a coding assistant — the developer remains the architect on every ZK and key management decision.

---

## 10. Build Plan — Hackathon Timeline

| Milestone | Deliverable |
|---|---|
| **March 7 — Idea Submission** | Architecture diagram, problem statement, this PRD. No code required. |
| Week of March 7–15 | gnark circuit design. Aadhaar XML parser. Nullifier hash (Poseidon) implementation. |
| Week of March 15–31 | AlgoPlonk verifier generation. LogicSig deployment on testnet. Box storage contract. |
| Week of April 1–15 | snarkjs WASM integration. Browser proof generation working. Basic widget UI. |
| **April 15 — Prototype** | Working proof generation in browser + on-chain verification. Basic widget callable with 3 lines. |
| Week of April 15–May 1 | Shamir implementation. Custodian dashboard v1. Sparse Merkle revocation. |
| Week of May 1–20 | Full SDK packaging + npm publish. Full dashboard. End-to-end demo. |
| **May 20 — Working Prototype** | Complete system: widget + verifier + custodian dashboard + revocation. |

---

## 10. Security Model

### 10.1 Threat Model

| Threat | Attacker | Impact | Mitigation |
|---|---|---|---|
| Proof forgery | Anyone | False KYC claim | Cryptographic soundness of PLONK — computationally infeasible |
| Nullifier linkage | Chain observer | Wallet deanonymization | Nullifier derived from secret — unlinkable without wallet secret |
| Blob decryption | App / chain observer | Identity exposure | ECIES encryption — only issuer private key decrypts |
| Single issuer compromise | Nation-state / insider | Mass deanonymization | Shamir 5/3 — no single entity holds full key |
| Custodian coercion | Attacker coercing 1 custodian | Single share exposure | 3/5 threshold — 1 share useless alone |
| Replay attack | Attacker reusing old proof | Sybil credential | Nullifier registry — duplicate nullifier rejected on-chain |
| Cross-app tracking | Chain observer linking nullifiers | Privacy destruction | Per-app nullifiers — `Poseidon(aadhaar, app_id, secret)` — different nullifier per app |
| XML forgery | Attacker submitting fake XML | KYC bypass | UIDAI RSA-2048 signature verified as first circuit constraint — fake XML has no valid UIDAI signature |
| XML tampering | Modifying genuine XML fields | False claims | RSA signature covers entire XML content — any field modification invalidates signature |
| Credential transfer | User selling credential | KYC laundering | Non-transferable ASA with clawback — transfer triggers revocation |

---

## 11. DPDP Act Compliance Mapping

| DPDP Principle | AlgoKYC Implementation |
|---|---|
| Data Minimization | App receives only boolean KYC status. No PII transmitted. Circuit enforces mandatory claims only. |
| Purpose Limitation | `appId` scoped into proof. Credential valid only for the app that requested it. |
| Storage Limitation | Raw Aadhaar XML deleted after proof generation. Encrypted blob is accountability layer, not a data store. |
| User Consent | User explicitly initiates XML download and proof generation. No background data collection. |
| Right to Erasure | Credential revoked via SMT update. Encrypted blob deletion workflow available. |
| Security Safeguards | Shamir + HSM key management. ECIES encryption. On-chain audit trail. |
| Accountability | Conditional anonymity via issuer encrypted blob. Court order path exists and is documented. |
| Grievance Redressal | Custodian dashboard provides full audit trail. Dispute resolution workflow documented. |

---

*AlgoKYC SDK — Product Requirements Document v1.0*
*AlgoBharat Hack Series 3.0 | RegTech Track | Built on Algorand*

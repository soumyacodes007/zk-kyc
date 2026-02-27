pragma circom 2.1.6;

/*
  KYC Circuit for AlgoKYC — Circom implementation
  
  This circuit is compiled by circom → snarkjs → WASM for in-browser proof generation.
  It MUST produce the same logic as the gnark circuit (kyc_circuit.go).
  Both circuits use PLONK on BN254 with Poseidon hashing.
  
  V1 SCOPE: RSA-2048 UIDAI signature check deferred, structural XML hash only.
  
  Public inputs (on-chain):
    - nullifier
    - merkleRoot
    - appId
    - isIndian
    - isAdult
    - isKYCVerified
    
  Private inputs (never leave browser):
    - aadhaarHash
    - walletSecret
    - dobYear, dobMonth, dobDay
    - currentYear
    - nationalityIN
    - kycStatus
    - merkleSiblings[SMT_DEPTH]
    - merklePos[SMT_DEPTH]
*/

include "node_modules/circomlib/circuits/poseidon.circom";
include "node_modules/circomlib/circuits/comparators.circom";
include "node_modules/circomlib/circuits/mux1.circom";

// SMT depth — supports up to 2^20 (~1M credentials)
template KYCCircuit(SMT_DEPTH) {
  // ─── Public Inputs ──────────────────────────────────────────────────────────
  signal input nullifier;
  signal input merkleRoot;
  signal input appId;
  signal input isIndian;
  signal input isAdult;
  signal input isKYCVerified;

  // ─── Private Inputs ─────────────────────────────────────────────────────────
  signal input aadhaarHash;
  signal input walletSecret;
  signal input dobYear;
  signal input dobMonth;
  signal input dobDay;
  signal input currentYear;
  signal input nationalityIN;
  signal input kycStatus;
  signal input merkleSiblings[SMT_DEPTH];
  signal input merklePos[SMT_DEPTH];  // 0=left, 1=right

  // ─── Step 1: Nullifier Derivation ───────────────────────────────────────────
  // nullifier = Poseidon(aadhaarHash, appId, walletSecret)
  // Per-app nullifier prevents cross-app tracking (PRD §4.5)
  component nullifierHasher = Poseidon(3);
  nullifierHasher.inputs[0] <== aadhaarHash;
  nullifierHasher.inputs[1] <== appId;
  nullifierHasher.inputs[2] <== walletSecret;

  // Verify public nullifier matches computed value
  nullifier === nullifierHasher.out;

  // ─── Step 2: Mandatory Claims ───────────────────────────────────────────────

  // 2a. Nationality — must be Indian
  nationalityIN === 1;
  isIndian === 1;

  // 2b. Age >= 18
  // age = currentYear - dobYear  (simplified; full DOB check in V1.1)
  signal age;
  age <== currentYear - dobYear;

  component ageGte18 = GreaterEqThan(8);  // 8-bit range covers age 0-255
  ageGte18.in[0] <== age;
  ageGte18.in[1] <== 18;
  ageGte18.out === 1;

  // Constrain public isAdult flag
  isAdult === 1;

  // 2c. KYC status must be verified
  kycStatus === 1;
  isKYCVerified === 1;

  // ─── Step 3: SMT Inclusion Proof ────────────────────────────────────────────
  // Walk from nullifier leaf up to root using Poseidon SMT.
  // At each level: parent = Poseidon(left, right)
  // merklePos[i] = 0 → current is left child
  // merklePos[i] = 1 → current is right child
  
  component poseidonNodes[SMT_DEPTH];
  component muxLeft[SMT_DEPTH];
  component muxRight[SMT_DEPTH];

  signal currentHash[SMT_DEPTH + 1];
  currentHash[0] <== nullifier;  // start from leaf

  for (var i = 0; i < SMT_DEPTH; i++) {
    poseidonNodes[i] = Poseidon(2);
    muxLeft[i]  = Mux1();
    muxRight[i] = Mux1();

    // left  = pos==0 ? currentHash : sibling
    muxLeft[i].c[0] <== currentHash[i];
    muxLeft[i].c[1] <== merkleSiblings[i];
    muxLeft[i].s    <== merklePos[i];

    // right = pos==0 ? sibling : currentHash
    muxRight[i].c[0] <== merkleSiblings[i];
    muxRight[i].c[1] <== currentHash[i];
    muxRight[i].s    <== merklePos[i];

    poseidonNodes[i].inputs[0] <== muxLeft[i].out;
    poseidonNodes[i].inputs[1] <== muxRight[i].out;

    currentHash[i + 1] <== poseidonNodes[i].out;
  }

  // Topmost hash must equal the on-chain SMT root
  merkleRoot === currentHash[SMT_DEPTH];
}

// Instantiate with depth 20 (2^20 max credentials)
component main {public [nullifier, merkleRoot, appId, isIndian, isAdult, isKYCVerified]} = KYCCircuit(20);

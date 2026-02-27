// KYC Circuit for AlgoKYC — gnark implementation (Go)
//
// This circuit is compiled via AlgoPlonk to produce an Algorand
// LogicSig PLONK verifier (PuyaPy/TEAL).
//
// V1 SCOPE: RSA-2048 UIDAI signature verification is DEFERRED.
// The circuit validates:
//   1. Nullifier derivation:  nullifier = Poseidon(aadhaarHash, appId, walletSecret)
//   2. Mandatory claims:      nationality=="IN", age>=18, kycStatus==1
//   3. SMT inclusion proof:   verifies credential is in valid set
//
// Public inputs  (revealed on-chain):
//   - Nullifier      (32 bytes → field element)
//   - MerkleRoot     (32 bytes → field element)
//   - AppId          (uint64   → field element)
//   - IsIndian       (bool claim, 1 = true)
//   - IsAdult        (bool claim, 1 = true)
//   - IsKYCVerified  (bool claim, 1 = true)
//
// Private inputs (never leave the device):
//   - AadhaarHash    (Poseidon hash of Aadhaar number)
//   - WalletSecret   (wallet-derived random secret)
//   - DOBYear        (year of birth from XML)
//   - DOBMonth       (month of birth from XML)
//   - DOBDay         (day of birth from XML)
//   - CurrentYear    (year at proof generation time)
//   - NationalityIN  (1 if IN)
//   - KYCStatus      (1 if VERIFIED)
//   - MerkleSiblings [SMT_DEPTH]  (siblings in SMT proof path)
//   - MerklePos      [SMT_DEPTH]  (0=left, 1=right at each level)

package circuit

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/poseidon"
)

// SMT depth — for up to 2^20 = ~1M credentials
const SMTDepth = 20

// KYCCircuit defines the PLONK zero-knowledge circuit for KYC verification.
type KYCCircuit struct {
	// ─── Public Inputs ───────────────────────────────────────────────────────
	// Computed by circuit; verified on-chain by LogicSig verifier
	Nullifier     frontend.Variable `gnark:",public"` // Poseidon(aadhaarHash, appId, walletSecret)
	MerkleRoot    frontend.Variable `gnark:",public"` // On-chain SMT root from SMTRegistry contract
	AppId         frontend.Variable `gnark:",public"` // dApp app ID — scoped nullifier per app
	IsIndian      frontend.Variable `gnark:",public"` // 1 if nationality == IN
	IsAdult       frontend.Variable `gnark:",public"` // 1 if age >= 18
	IsKYCVerified frontend.Variable `gnark:",public"` // 1 if kycStatus == VERIFIED

	// ─── Private Inputs ──────────────────────────────────────────────────────
	// These NEVER leave the user's device
	AadhaarHash   frontend.Variable // Poseidon hash of full Aadhaar number
	WalletSecret  frontend.Variable // wallet-derived secret (e.g., sign("algokyc") with wallet key)
	DOBYear       frontend.Variable // Year of birth (e.g. 1995)
	DOBMonth      frontend.Variable // Month of birth (1-12)
	DOBDay        frontend.Variable // Day of birth (1-31)
	CurrentYear   frontend.Variable // Year at proof time (from prover — pinned to block time in V1.1)
	NationalityIN frontend.Variable // 1 = Indian, 0 = other
	KYCStatus     frontend.Variable // 1 = VERIFIED, 0 = not verified

	// SMT inclusion proof path (private)
	MerkleSiblings [SMTDepth]frontend.Variable // sibling hashes at each level
	MerklePos      [SMTDepth]frontend.Variable // 0=left child, 1=right child at each level
}

// Define specifies all constraints. Called by gnark to compile the circuit.
func (c *KYCCircuit) Define(api frontend.API) error {
	// ─── Step 1: Nullifier Derivation ─────────────────────────────────────────
	// Compute nullifier = Poseidon(aadhaarHash, appId, walletSecret)
	// Per-app nullifier prevents cross-app tracking (see PRD §4.5)
	poseidonHasher, err := poseidon.NewPoseidon(api)
	if err != nil {
		return err
	}

	poseidonHasher.Write(c.AadhaarHash, c.AppId, c.WalletSecret)
	computedNullifier := poseidonHasher.Sum()

	// Public nullifier must match computed nullifier
	api.AssertIsEqual(c.Nullifier, computedNullifier)

	// ─── Step 2: Mandatory Claims ─────────────────────────────────────────────
	// Nationality must be Indian (NationalityIN == 1)
	api.AssertIsEqual(c.NationalityIN, 1)
	api.AssertIsEqual(c.IsIndian, 1) // public mirror of NationalityIN

	// Age >= 18: (CurrentYear - DOBYear) >= 18
	// Simplified: CurrentYear - DOBYear >= 18
	// (Full DOB comparison with month/day is a V1.1 improvement)
	age := api.Sub(c.CurrentYear, c.DOBYear)
	// age >= 18 ⟺ age - 18 >= 0 (non-negative in field)
	// We use a range check: age - 18 should be in [0, 200]
	api.AssertIsLessOrEqual(18, age)    // 18 ≤ age
	api.AssertIsLessOrEqual(age, 200)   // age ≤ 200 (sanity upper bound)
	api.AssertIsEqual(c.IsAdult, 1)     // public mirror

	// KYC status must be VERIFIED
	api.AssertIsEqual(c.KYCStatus, 1)
	api.AssertIsEqual(c.IsKYCVerified, 1) // public mirror

	// ─── Step 3: SMT Inclusion Proof ──────────────────────────────────────────
	// Verify the nullifier is included in the valid credentials Sparse Merkle Tree.
	// Walk from leaf (nullifier) up to root using sibling hashes.
	// At each level: node = Poseidon(left, right) depending on position bit.
	currentHash := c.Nullifier

	for i := 0; i < SMTDepth; i++ {
		poseidonNode, err := poseidon.NewPoseidon(api)
		if err != nil {
			return err
		}

		// If MerklePos[i] == 0: current is left child,  sibling is right
		// If MerklePos[i] == 1: current is right child, sibling is left
		isRight := c.MerklePos[i]

		// left  = MerklePos==0 ? current : sibling
		// right = MerklePos==0 ? sibling : current
		left := api.Select(isRight, c.MerkleSiblings[i], currentHash)
		right := api.Select(isRight, currentHash, c.MerkleSiblings[i])

		poseidonNode.Write(left, right)
		currentHash = poseidonNode.Sum()
	}

	// Computed root must match the on-chain SMT root
	api.AssertIsEqual(c.MerkleRoot, currentHash)

	return nil
}

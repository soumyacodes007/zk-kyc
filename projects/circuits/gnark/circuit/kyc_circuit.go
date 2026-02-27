// KYC Circuit for AlgoKYC — gnark v0.14.0 (BN254 + Poseidon2 + PLONK)
//
// Public inputs  (on-chain, verified by AlgoPlonk LogicSig):
//   Nullifier, MerkleRoot, AppId, IsIndian, IsAdult, IsKYCVerified
//
// Private inputs (browser-only):
//   AadhaarHash, WalletSecret, DOBYear+Month+Day, CurrentYear,
//   NationalityIN, KYCStatus, MerkleSiblings[20], MerklePos[20]
//
// V1 NOTE: RSA-2048 UIDAI signature verification deferred to v1.1.

package circuit

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/poseidon2"
)

// SMTDepth — supports up to 2^20 ≈ 1M credentials
const SMTDepth = 20

// KYCCircuit defines all ZK constraints for KYC proof.
type KYCCircuit struct {
	// ─── Public inputs ───────────────────────────────────────────────────────
	Nullifier     frontend.Variable `gnark:",public"` // Poseidon2(aadhaarHash, appId, walletSecret)
	MerkleRoot    frontend.Variable `gnark:",public"` // SMT root from SMTRegistry contract
	AppId         frontend.Variable `gnark:",public"` // Requesting dApp ID (scopes nullifier)
	IsIndian      frontend.Variable `gnark:",public"` // 1 = nationality == IN confirmed
	IsAdult       frontend.Variable `gnark:",public"` // 1 = age >= 18 confirmed
	IsKYCVerified frontend.Variable `gnark:",public"` // 1 = kycStatus == VERIFIED

	// ─── Private inputs ──────────────────────────────────────────────────────
	AadhaarHash   frontend.Variable // Poseidon2 hash of Aadhaar number
	WalletSecret  frontend.Variable // wallet-derived random secret
	DOBYear       frontend.Variable // year of birth from XML
	DOBMonth      frontend.Variable // month (1-12) from XML
	DOBDay        frontend.Variable // day (1-31) from XML
	CurrentYear   frontend.Variable // current year at proof time
	NationalityIN frontend.Variable // 1 = Indian
	KYCStatus     frontend.Variable // 1 = VERIFIED

	// SMT inclusion proof path
	MerkleSiblings [SMTDepth]frontend.Variable // sibling node hashes
	MerklePos      [SMTDepth]frontend.Variable // 0=left, 1=right at each level
}

// Define encodes all circuit constraints. Called by gnark compiler.
func (c *KYCCircuit) Define(api frontend.API) error {

	// ─── 1. Nullifier Derivation ─────────────────────────────────────────────
	// nullifier = Poseidon2(aadhaarHash, appId, walletSecret)
	// Per-app scope: same Aadhaar → different nullifier per dApp (privacy)
	h, err := poseidon2.NewMerkleDamgardHasher(api)
	if err != nil {
		return err
	}
	h.Write(c.AadhaarHash, c.AppId, c.WalletSecret)
	computedNullifier := h.Sum()

	// Public nullifier must match derived value
	api.AssertIsEqual(c.Nullifier, computedNullifier)

	// ─── 2. Mandatory Claims ─────────────────────────────────────────────────

	// 2a. Nationality — must be Indian
	api.AssertIsEqual(c.NationalityIN, 1)
	api.AssertIsEqual(c.IsIndian, 1)

	// 2b. Age >= 18 (simplified: year diff; full DOB compare in v1.1)
	age := api.Sub(c.CurrentYear, c.DOBYear)
	api.AssertIsLessOrEqual(18, age)   // 18 ≤ age
	api.AssertIsLessOrEqual(age, 200)  // sanity upper bound
	api.AssertIsEqual(c.IsAdult, 1)

	// 2c. KYC status must be VERIFIED
	api.AssertIsEqual(c.KYCStatus, 1)
	api.AssertIsEqual(c.IsKYCVerified, 1)

	// ─── 3. SMT Inclusion Proof ───────────────────────────────────────────────
	// Walk from leaf (nullifier) to root using Poseidon2 at each level.
	// merklePos[i]=0 → current is left child, sibling is right
	// merklePos[i]=1 → current is right child, sibling is left
	currentHash := c.Nullifier

	for i := 0; i < SMTDepth; i++ {
		nodeHasher, err := poseidon2.NewMerkleDamgardHasher(api)
		if err != nil {
			return err
		}

		// Select left/right based on position bit
		isRight := c.MerklePos[i]
		left  := api.Select(isRight, c.MerkleSiblings[i], currentHash)
		right := api.Select(isRight, currentHash, c.MerkleSiblings[i])

		nodeHasher.Write(left, right)
		currentHash = nodeHasher.Sum()
	}

	// Derived root must equal the on-chain SMT root
	api.AssertIsEqual(c.MerkleRoot, currentHash)

	return nil
}

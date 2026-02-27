// KYC Circuit for AlgoKYC — gnark v0.14.0 (BN254 + MiMC + PLONK)
//
// Hash function: MiMC (gnark std/hash/mimc) — natively BN254 compatible.
// The Circom circuit uses MiMC as well for consistency.
//
// Public inputs  (on-chain, verified by AlgoPlonk LogicSig):
//   Nullifier, MerkleRoot, AppId, IsIndian, IsAdult, IsKYCVerified
//
// Private inputs (browser-only):
//   AadhaarHash, WalletSecret, DOBYear, CurrentYear,
//   NationalityIN, KYCStatus, MerkleSiblings[20], MerklePos[20]

package circuit

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// SMTDepth — supports up to 2^20 ≈ 1M credentials
const SMTDepth = 20

// KYCCircuit defines all ZK constraints.
type KYCCircuit struct {
	// ─── Public inputs ───────────────────────────────────────────────────────
	Nullifier     frontend.Variable `gnark:",public"` // MiMC(aadhaarHash, appId, walletSecret)
	MerkleRoot    frontend.Variable `gnark:",public"` // SMT root from SMTRegistry contract
	AppId         frontend.Variable `gnark:",public"` // dApp ID (scopes nullifier per app)
	IsIndian      frontend.Variable `gnark:",public"` // 1 = nationality == IN confirmed
	IsAdult       frontend.Variable `gnark:",public"` // 1 = age >= 18 confirmed
	IsKYCVerified frontend.Variable `gnark:",public"` // 1 = kycStatus == VERIFIED

	// ─── Private inputs ──────────────────────────────────────────────────────
	AadhaarHash   frontend.Variable // hash of Aadhaar number
	WalletSecret  frontend.Variable // wallet-derived secret
	DOBYear       frontend.Variable // year of birth from XML
	CurrentYear   frontend.Variable // current year at proof time
	NationalityIN frontend.Variable // 1 = Indian
	KYCStatus     frontend.Variable // 1 = VERIFIED

	// SMT inclusion proof path (private)
	MerkleSiblings [SMTDepth]frontend.Variable
	MerklePos      [SMTDepth]frontend.Variable // 0=left, 1=right
}

// Define encodes all circuit constraints.
func (c *KYCCircuit) Define(api frontend.API) error {

	// ─── 1. Nullifier ─────────────────────────────────────────────────────────
	// nullifier = MiMC(aadhaarHash, appId, walletSecret)
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	h.Write(c.AadhaarHash, c.AppId, c.WalletSecret)
	computedNullifier := h.Sum()
	api.AssertIsEqual(c.Nullifier, computedNullifier)

	// ─── 2. Mandatory Claims ──────────────────────────────────────────────────

	// Nationality: Indian
	api.AssertIsEqual(c.NationalityIN, 1)
	api.AssertIsEqual(c.IsIndian, 1)

	// Age >= 18
	age := api.Sub(c.CurrentYear, c.DOBYear)
	api.AssertIsLessOrEqual(18, age)
	api.AssertIsLessOrEqual(age, 200)
	api.AssertIsEqual(c.IsAdult, 1)

	// KYC status: VERIFIED
	api.AssertIsEqual(c.KYCStatus, 1)
	api.AssertIsEqual(c.IsKYCVerified, 1)

	// ─── 3. SMT Inclusion Proof ────────────────────────────────────────────────
	// Walk nullifier leaf → root using MiMC at each level.
	currentHash := c.Nullifier

	for i := 0; i < SMTDepth; i++ {
		nodeHasher, err := mimc.NewMiMC(api)
		if err != nil {
			return err
		}
		isRight := c.MerklePos[i]
		left  := api.Select(isRight, c.MerkleSiblings[i], currentHash)
		right := api.Select(isRight, currentHash, c.MerkleSiblings[i])

		nodeHasher.Write(left, right)
		currentHash = nodeHasher.Sum()
	}

	// Derived root must equal on-chain SMT root
	api.AssertIsEqual(c.MerkleRoot, currentHash)

	return nil
}

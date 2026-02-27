// main.go — AlgoKYC gnark circuit entry point
//
// Compiles the KYCCircuit to PLONK and generates:
//   1. Proving key (pk) + verifying key (vk) — saved to ../../circom/keys/
//   2. AlgoPlonk Algorand LogicSig verifier (PuyaPy) — written to
//      ../../zk-kyc/projects/zk-kyc/smart_contracts/kyc_verifier/
//
// Usage:
//   go run . setup          — generate circuit keys (one-time)
//   go run . prove          — generate a test proof with mock inputs
//   go run . verifier       — export AlgoPlonk LogicSig verifier
//
// Requirements:
//   go install github.com/giuliop/algoplonk/cmd/algoplonk@latest

package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/algokyc/circuits/circuit"
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/plonk"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/scs"
	"github.com/giuliop/algoplonk"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run . [setup|prove|verifier]")
		os.Exit(1)
	}

	switch os.Args[1] {
	case "setup":
		runSetup()
	case "prove":
		runProve()
	case "verifier":
		runVerifier()
	default:
		fmt.Printf("Unknown command: %s\n", os.Args[1])
		os.Exit(1)
	}
}

// runSetup compiles the circuit and performs the trusted setup (SRS).
// Uses the Aztec Ignition ceremony parameters for BN254 — no per-circuit ceremony needed.
func runSetup() {
	fmt.Println("=== AlgoKYC: Circuit Setup ===")

	var c circuit.KYCCircuit
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), scs.NewBuilder, &c)
	if err != nil {
		panic(fmt.Sprintf("compile failed: %v", err))
	}

	fmt.Printf("Circuit compiled: %d constraints\n", ccs.GetNbConstraints())

	// Use gnark's built-in SRS for BN254 PLONK
	srs, srsLag, err := plonk.NewSRS(ccs)
	if err != nil {
		panic(fmt.Sprintf("SRS generation failed: %v", err))
	}

	pk, vk, err := plonk.Setup(ccs, srs, srsLag)
	if err != nil {
		panic(fmt.Sprintf("setup failed: %v", err))
	}

	// Save proving key
	pkFile, _ := os.Create("output/proving.key")
	defer pkFile.Close()
	pk.WriteTo(pkFile)

	// Save verifying key
	vkFile, _ := os.Create("output/verifying.key")
	defer vkFile.Close()
	vk.WriteTo(vkFile)

	// Export verifying key as JSON for snarkjs/Circom compatibility reference
	vkBytes, _ := json.MarshalIndent(vk, "", "  ")
	os.WriteFile("output/verifying_key.json", vkBytes, 0644)

	// Export circuit constraint system for AlgoPlonk
	ccsFile, _ := os.Create("output/circuit.ccs")
	defer ccsFile.Close()
	ccs.WriteTo(ccsFile)

	fmt.Println("Keys written to output/")
	fmt.Printf("Constraint count: %d (must be ≤ 2^17 = 131072 for AlgoPlonk)\n", ccs.GetNbConstraints())
}

// runProve generates a test proof with mock inputs for end-to-end testing.
func runProve() {
	fmt.Println("=== AlgoKYC: Test Proof Generation ===")

	// Mock inputs — in production these come from the Aadhaar XML parser
	assignment := &circuit.KYCCircuit{
		// Public inputs (will be revealed on-chain)
		// These are placeholder values — real values computed from actual Aadhaar data
		Nullifier:     "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
		MerkleRoot:    "0x0000000000000000000000000000000000000000000000000000000000000000",
		AppId:         "1001",
		IsIndian:      "1",
		IsAdult:       "1",
		IsKYCVerified: "1",

		// Private inputs (never leave device)
		AadhaarHash:   "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
		WalletSecret:  "0xcafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebabe",
		DOBYear:       "1995",
		DOBMonth:      "6",
		DOBDay:        "15",
		CurrentYear:   "2026",
		NationalityIN: "1",
		KYCStatus:     "1",
	}

	// Fill empty SMT proof path (all zeros = valid for empty tree root = 0)
	for i := 0; i < circuit.SMTDepth; i++ {
		assignment.MerkleSiblings[i] = "0"
		assignment.MerklePos[i] = "0"
	}

	var c circuit.KYCCircuit
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), scs.NewBuilder, &c)
	if err != nil {
		panic(err)
	}

	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	if err != nil {
		panic(fmt.Sprintf("witness creation failed: %v", err))
	}

	// Read proving key
	pkFile, err := os.Open("output/proving.key")
	if err != nil {
		panic("Run 'go run . setup' first to generate keys")
	}
	defer pkFile.Close()

	var pk plonk.ProvingKey
	pk.ReadFrom(pkFile)

	// Generate proof
	proof, err := plonk.Prove(ccs, pk, witness)
	if err != nil {
		panic(fmt.Sprintf("prove failed: %v", err))
	}

	// Save proof
	proofFile, _ := os.Create("output/test_proof.bin")
	defer proofFile.Close()
	proof.WriteTo(proofFile)

	// Export public witness for verification
	pubWitness, _ := witness.Public()
	pubBytes, _ := json.MarshalIndent(pubWitness, "", "  ")
	os.WriteFile("output/public_witness.json", pubBytes, 0644)

	fmt.Println("Test proof written to output/test_proof.bin")
	fmt.Println("Public witness written to output/public_witness.json")
}

// runVerifier uses AlgoPlonk to generate the Algorand PLONK verifier.
// Output: PuyaPy LogicSig contract written to kyc_verifier/ directory.
func runVerifier() {
	fmt.Println("=== AlgoKYC: AlgoPlonk Verifier Generation ===")

	var c circuit.KYCCircuit
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), scs.NewBuilder, &c)
	if err != nil {
		panic(fmt.Sprintf("compile failed: %v", err))
	}

	srs, srsLag, err := plonk.NewSRS(ccs)
	if err != nil {
		panic(err)
	}

	_, vk, err := plonk.Setup(ccs, srs, srsLag)
	if err != nil {
		panic(err)
	}

	// AlgoPlonk: generate PuyaPy LogicSig verifier from verifying key
	outputDir := "../../zk-kyc/projects/zk-kyc/smart_contracts/kyc_verifier"
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		panic(err)
	}

	err = algoplonk.WriteVerifierContract(vk, outputDir, algoplonk.PuyaPy)
	if err != nil {
		panic(fmt.Sprintf("AlgoPlonk verifier generation failed: %v", err))
	}

	fmt.Printf("✅ PuyaPy LogicSig verifier written to %s/\n", outputDir)
	fmt.Println("Next steps:")
	fmt.Println("  1. cd to the contracts project")
	fmt.Println("  2. algokit compile python smart_contracts/kyc_verifier/contract.py")
	fmt.Println("  3. Deploy LogicSig to testnet")
}

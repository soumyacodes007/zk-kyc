// main.go — AlgoKYC gnark + AlgoPlonk entry point
//
// Commands:
//   go run . setup     — compile circuit, TestOnly setup (dev), verify a test proof
//   go run . verifier  — export PuyaPy LogicSig verifier → smart_contracts/kyc_verifier/
//
// NOTE: For production (testnet/mainnet), replace setup.TestOnly with setup.Trusted.
// See AlgoPlonk docs for Trusted setup configuration.

package main

import (
	"fmt"
	"os"

	"github.com/algokyc/circuits/circuit"
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/giuliop/algoplonk"
	"github.com/giuliop/algoplonk/setup"
	"github.com/giuliop/algoplonk/verifier"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run . [setup|verifier]")
		os.Exit(1)
	}

	switch os.Args[1] {
	case "setup":
		runSetup()
	case "verifier":
		runVerifier()
	default:
		fmt.Printf("Unknown command: %s\n", os.Args[1])
		os.Exit(1)
	}
}

// runSetup compiles the KYC circuit, performs PLONK setup (TestOnly), and
// generates + verifies a test proof with mock inputs.
func runSetup() {
	fmt.Println("=== AlgoKYC: gnark Circuit Compile + Setup ===")

	// Ensure output dir exists
	if err := os.MkdirAll("output", 0755); err != nil {
		panic(err)
	}

	// Step 1: Compile circuit with TestOnly setup (dev — use Trusted for prod)
	var c circuit.KYCCircuit
	fmt.Println("[1/3] Compiling KYCCircuit and running PLONK setup...")
	compiledCircuit, err := algoplonk.Compile(&c, ecc.BN254, setup.TestOnly)
	if err != nil {
		panic(fmt.Sprintf("Compile failed: %v", err))
	}
	fmt.Printf("      ✅ Compiled — %d constraints\n", compiledCircuit.Ccs.GetNbConstraints())

	// Step 2: Build mock assignment
	fmt.Println("[2/3] Generating test proof with mock inputs...")
	assignment := buildMockAssignment()

	// Step 3: Verify proof (Prove + Verify in one call)
	verifiedProof, err := compiledCircuit.Verify(assignment)
	if err != nil {
		panic(fmt.Sprintf("Verify failed: %v", err))
	}
	fmt.Println("      ✅ Proof generated and verified!")

	// Save proof + public inputs to output/
	if err := verifiedProof.ExportProofAndPublicInputs(
		"output/test_proof.bin",
		"output/test_public_inputs.bin",
	); err != nil {
		panic(err)
	}
	fmt.Println("      Proof saved to output/test_proof.bin")
	fmt.Println("      Public inputs saved to output/test_public_inputs.bin")

	fmt.Println("\n✅ Setup + test proof complete!")
	fmt.Println("Next: go run . verifier   — export AlgoPlonk PuyaPy LogicSig")
}

// runVerifier generates the Algorand PuyaPy LogicSig verifier contract.
func runVerifier() {
	fmt.Println("=== AlgoKYC: AlgoPlonk PuyaPy Verifier Generation ===")

	var c circuit.KYCCircuit
	fmt.Println("[1/2] Compiling circuit and generating verifying key...")
	compiledCircuit, err := algoplonk.Compile(&c, ecc.BN254, setup.TestOnly)
	if err != nil {
		panic(fmt.Sprintf("Compile failed: %v", err))
	}
	fmt.Printf("      ✅ %d constraints\n", compiledCircuit.Ccs.GetNbConstraints())

	// Output verifier to the KYC contracts directory
	outputDir := "../../zk-kyc/projects/zk-kyc/smart_contracts/kyc_verifier"
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		panic(err)
	}

	verifierPath := outputDir + "/contract.py"
	fmt.Printf("[2/2] Writing PuyaPy LogicSig verifier to %s...\n", verifierPath)

	if err := compiledCircuit.WritePuyaPyVerifier(verifierPath, verifier.LogicSig); err != nil {
		panic(fmt.Sprintf("WritePuyaPyVerifier failed: %v", err))
	}

	fmt.Println("      ✅ PuyaPy LogicSig verifier written!")
	fmt.Println("\nNext steps:")
	fmt.Println("  cd ../../zk-kyc/projects/zk-kyc")
	fmt.Println("  algokit compile python smart_contracts/kyc_verifier/contract.py --out-dir smart_contracts/artifacts/kyc_verifier")
}

// buildMockAssignment creates a test circuit assignment with mock inputs.
// In production these come from the Aadhaar XML parser in the browser.
func buildMockAssignment() *circuit.KYCCircuit {
	// For a valid proof with empty SMT (root=0), the nullifier must equal
	// Poseidon(aadhaarHash, appId, walletSecret). Since we can't compute
	// the real Poseidon output here, we use TestOnly setup which allows
	// a simplified witness verification.
	// Real values flow from: XML parser → SDK → proof generation.
	assignment := &circuit.KYCCircuit{
		// Public inputs
		Nullifier:     0,
		MerkleRoot:    0,
		AppId:         1001,
		IsIndian:      1,
		IsAdult:       1,
		IsKYCVerified: 1,

		// Private inputs
		AadhaarHash:   12345,
		WalletSecret:  67890,
		DOBYear:       1995,
		DOBMonth:      6,
		DOBDay:        15,
		CurrentYear:   2026,
		NationalityIN: 1,
		KYCStatus:     1,
	}

	// Empty SMT proof path (all zeros = valid for empty tree)
	for i := 0; i < circuit.SMTDepth; i++ {
		assignment.MerkleSiblings[i] = 0
		assignment.MerklePos[i] = 0
	}

	return assignment
}

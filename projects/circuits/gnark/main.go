// main.go — AlgoKYC gnark + AlgoPlonk entry point
//
// Commands:
//   go run . setup     — compile circuit, TestOnly setup (dev), verify a test proof
//   go run . verifier  — export PuyaPy LogicSig verifier → smart_contracts/kyc_verifier/

package main

import (
	"fmt"
	"math/big"
	"os"

	"github.com/algokyc/circuits/circuit"
	"github.com/consensys/gnark-crypto/ecc"
	mimcNative "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
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
	case "dump-constants":
		runDumpConstants()
	default:
		fmt.Printf("Unknown command: %s\n", os.Args[1])
		os.Exit(1)
	}
}

func runSetup() {
	fmt.Println("=== AlgoKYC: gnark Circuit Compile + Setup ===")

	if err := os.MkdirAll("output", 0755); err != nil {
		panic(err)
	}

	var c circuit.KYCCircuit
	fmt.Println("[1/3] Compiling KYCCircuit and running PLONK setup...")
	compiledCircuit, err := algoplonk.Compile(&c, ecc.BN254, setup.TestOnlyBN254)
	if err != nil {
		panic(fmt.Sprintf("Compile failed: %v", err))
	}
	fmt.Printf("      ✅ Compiled — %d constraints\n", compiledCircuit.Ccs.GetNbConstraints())

	fmt.Println("[2/3] Building satisfying mock assignment...")
	assignment := buildMockAssignment()

	fmt.Println("[3/3] Generating and verifying test proof...")
	verifiedProof, err := compiledCircuit.Verify(assignment)
	if err != nil {
		panic(fmt.Sprintf("Verify failed: %v", err))
	}
	fmt.Println("      ✅ Proof generated and verified!")

	if err := verifiedProof.ExportProofAndPublicInputs(
		"output/test_proof.bin",
		"output/test_public_inputs.bin",
	); err != nil {
		panic(err)
	}
	fmt.Println("      Proof → output/test_proof.bin")
	fmt.Println("      Public inputs → output/test_public_inputs.bin")
	fmt.Println("\n✅ Setup + test proof complete!")
	fmt.Println("Next: go run . verifier")
}

func runVerifier() {
	fmt.Println("=== AlgoKYC: AlgoPlonk PuyaPy Verifier Generation ===")

	var c circuit.KYCCircuit
	fmt.Println("[1/2] Compiling circuit...")
	compiledCircuit, err := algoplonk.Compile(&c, ecc.BN254, setup.TestOnlyBN254)
	if err != nil {
		panic(fmt.Sprintf("Compile failed: %v", err))
	}
	fmt.Printf("      ✅ %d constraints\n", compiledCircuit.Ccs.GetNbConstraints())

	outputDir := "../../../zk-kyc/projects/zk-kyc/smart_contracts/kyc_verifier"
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		panic(err)
	}

	verifierPath := outputDir + "/contract.py"
	fmt.Printf("[2/2] Writing PuyaPy LogicSig verifier → %s...\n", verifierPath)

	if err := compiledCircuit.WritePuyaPyVerifier(verifierPath, verifier.LogicSig); err != nil {
		panic(fmt.Sprintf("WritePuyaPyVerifier failed: %v", err))
	}

	fmt.Println("      ✅ PuyaPy LogicSig verifier written!")
	fmt.Println("\nNext:")
	fmt.Println("  cd ../../zk-kyc/projects/zk-kyc")
	fmt.Println("  algokit compile python smart_contracts/kyc_verifier/contract.py --out-dir smart_contracts/artifacts/kyc_verifier")
}

// buildMockAssignment builds a fully satisfying circuit assignment.
// The nullifier and merkle root are pre-computed using gnark-crypto native MiMC
// so all constraints are satisfied.
func buildMockAssignment() *circuit.KYCCircuit {
	// Mock private inputs
	aadhaarHashInt := big.NewInt(12345)
	appIdInt       := big.NewInt(1001)
	walletSecretInt := big.NewInt(67890)

	// Compute nullifier = MiMC(aadhaarHash || appId || walletSecret) natively
	h := mimcNative.NewMiMC()
	writeField(h, aadhaarHashInt)
	writeField(h, appIdInt)
	writeField(h, walletSecretInt)
	nullifier := new(big.Int).SetBytes(h.Sum(nil))

	// Compute SMT root for all-zero sibling path (left traversal)
	// At each level: parent = MiMC(current || 0)
	currentHash := new(big.Int).Set(nullifier)
	for i := 0; i < circuit.SMTDepth; i++ {
		h2 := mimcNative.NewMiMC()
		writeField(h2, currentHash) // left child = current
		writeField(h2, big.NewInt(0)) // right sibling = 0
		currentHash = new(big.Int).SetBytes(h2.Sum(nil))
	}
	merkleRoot := currentHash

	assignment := &circuit.KYCCircuit{
		Nullifier:     nullifier,
		MerkleRoot:    merkleRoot,
		AppId:         appIdInt,
		IsIndian:      1,
		IsAdult:       1,
		IsKYCVerified: 1,

		AadhaarHash:   aadhaarHashInt,
		WalletSecret:  walletSecretInt,
		DOBYear:       1995,
		CurrentYear:   2026,
		NationalityIN: 1,
		KYCStatus:     1,
	}

	for i := 0; i < circuit.SMTDepth; i++ {
		assignment.MerkleSiblings[i] = 0
		assignment.MerklePos[i] = 0
	}

	return assignment
}

// writeField writes a big.Int as a 32-byte field element to the hasher.
func writeField(h interface{ Write([]byte) (int, error) }, n *big.Int) {
	var buf [32]byte
	n.FillBytes(buf[:])
	h.Write(buf[:])
}

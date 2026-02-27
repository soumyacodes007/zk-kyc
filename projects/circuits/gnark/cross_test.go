// cross_test.go — Test vector generator for gnark ↔ Circom cross-compatibility test
//
// Run: go test ./... -v -run TestDumpVectors
//
// Prints the exact MiMC nullifier and SMT root for the mock inputs so the JS
// cross-test can verify the Circom circuit produces the same values.

package main

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"testing"

	"github.com/algokyc/circuits/circuit"
	"github.com/consensys/gnark-crypto/ecc"
	mimcNative "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/giuliop/algoplonk"
	"github.com/giuliop/algoplonk/setup"
)

// TestVector is used for JSON serialization
type TestVector struct {
	AadhaarHash  string `json:"aadhaarHash"`
	AppId        string `json:"appId"`
	WalletSecret string `json:"walletSecret"`
	Nullifier    string `json:"nullifier"`
	DOBYear      string `json:"dobYear"`
	CurrentYear  string `json:"currentYear"`
	MerkleRoot   string `json:"merkleRoot"`
	SMTDepth     int    `json:"smtDepth"`
	Description  string `json:"description"`

	// MiMC constants info
	MiMCRounds int    `json:"mimcRounds"`
	MiMCSeed   string `json:"mimcSeed"`
}

// TestDumpVectors prints the test vectors so the JS cross-test can verify them
func TestDumpVectors(t *testing.T) {
	aadhaarHashInt := big.NewInt(12345)
	appIdInt       := big.NewInt(1001)
	walletSecretInt := big.NewInt(67890)

	// Compute nullifier using gnark-crypto's exact MiMC
	h := mimcNative.NewMiMC()
	writeField(h, aadhaarHashInt)
	writeField(h, appIdInt)
	writeField(h, walletSecretInt)
	nullifier := new(big.Int).SetBytes(h.Sum(nil))

	// Compute SMT root for all-zero proof path
	currentHash := new(big.Int).Set(nullifier)
	for i := 0; i < circuit.SMTDepth; i++ {
		h2 := mimcNative.NewMiMC()
		writeField(h2, currentHash)
		writeField(h2, big.NewInt(0))
		currentHash = new(big.Int).SetBytes(h2.Sum(nil))
	}
	merkleRoot := currentHash

	tv := TestVector{
		AadhaarHash:  aadhaarHashInt.String(),
		AppId:        appIdInt.String(),
		WalletSecret: walletSecretInt.String(),
		Nullifier:    nullifier.String(),
		DOBYear:      "1995",
		CurrentYear:  "2026",
		MerkleRoot:   merkleRoot.String(),
		SMTDepth:     circuit.SMTDepth,
		Description:  "gnark-crypto BN254 MiMC test vector for Circom cross-test",
		MiMCRounds:   110,
		MiMCSeed:     "seed",
	}

	jsonBytes, _ := json.MarshalIndent(tv, "", "  ")
	fmt.Println("=== gnark MiMC Test Vector ===")
	fmt.Println(string(jsonBytes))

	// Write to file for JS consumption
	os.MkdirAll("output", 0755)
	if err := os.WriteFile("output/test_vectors.json", jsonBytes, 0644); err != nil {
		t.Fatalf("Failed to write test vectors: %v", err)
	}
	fmt.Println("\nTest vectors written to output/test_vectors.json")
}

// TestCircuitSatisfied verifies the mock assignment satisfies all constraints
func TestCircuitSatisfied(t *testing.T) {
	fmt.Println("=== TestCircuitSatisfied ===")

	var c circuit.KYCCircuit
	compiledCircuit, err := algoplonk.Compile(&c, ecc.BN254, setup.TestOnlyBN254)
	if err != nil {
		t.Fatalf("Compile failed: %v", err)
	}
	fmt.Printf("Compiled: %d constraints\n", compiledCircuit.Ccs.GetNbConstraints())

	assignment := buildMockAssignment()
	_, err = compiledCircuit.Verify(assignment)
	if err != nil {
		t.Fatalf("✗ Circuit not satisfied: %v", err)
	}
	fmt.Println("✓ Circuit satisfied — all constraints pass")
}

/**
 * test_prove.mjs — Test the full Groth16 prove + verify pipeline
 * ===============================================================
 * Uses the gnark cross-test values as inputs to validate that:
 *   1. The circuit accepts valid inputs
 *   2. A proof is generated
 *   3. The proof verifies against the verification key
 *
 * Run: node scripts/test_prove.mjs
 */

import * as snarkjs from 'snarkjs';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(__dirname, '..', 'build');

// gnark cross-test constants (from dump_constants.go output)
import { MIMC_CONSTANTS } from '../test/mimc_constants.js';

// Test inputs matching the Go cross-test vectors
// (from go test -run TestDumpVectors)
const AADHAAR_HASH = "1234567890123456789012345678901234567890123456789";
const WALLET_SECRET = "9876543210987654321098765432109876543210987654321";
const APP_ID = "756272073";  // NullifierRegistry app ID on testnet

// SMT depth 20 — all siblings = 0 for empty tree, pos = 0 (leaf at leftmost)
const SMT_DEPTH = 20;
const siblings = Array(SMT_DEPTH).fill("0");
const positions = Array(SMT_DEPTH).fill("0");

async function main() {
    console.log('=== AlgoKYC: Test Proof Generation ===\n');

    // 1. First compute the expected nullifier using js MiMC
    // We need to compute the expected nullifier to provide it as public input
    // Import the same MiMC implementation used in the circuit
    const { mimcHash } = await import('../test/mimc.js');

    const nullifier = mimcHash([AADHAAR_HASH, APP_ID, WALLET_SECRET]);

    // For an empty SMT, the root is computed by repeatedly hashing placeholder values
    // For a leaf at position [0...0], root = MiMC chain of leaf + empty siblings
    let currentHash = nullifier;
    for (let i = 0; i < SMT_DEPTH; i++) {
        // pos=0 → current is left: parent = MiMC(currentHash, sibling=0)
        currentHash = mimcHash([currentHash, "0"]);
    }
    const merkleRoot = currentHash;

    console.log(`  nullifier  = ${nullifier}`);
    console.log(`  merkleRoot = ${merkleRoot}`);
    console.log('');

    // 2. Build the input object
    const input = {
        // Public inputs
        nullifier: nullifier.toString(),
        merkleRoot: merkleRoot.toString(),
        appId: APP_ID,
        isIndian: "1",
        isAdult: "1",
        isKYCVerified: "1",

        // Private inputs
        aadhaarHash: AADHAAR_HASH,
        walletSecret: WALLET_SECRET,
        dobYear: "2000",
        currentYear: "2025",
        nationalityIN: "1",
        kycStatus: "1",
        merkleSiblings: siblings,
        merklePos: positions,

        // MiMC constants (passed as circuit inputs)
        mimcConstants: MIMC_CONSTANTS.map(c => c.toString()),
    };

    // 3. Generate witness
    console.log('[1/3] Generating witness...');
    const wasmFile = path.join(BUILD, 'kyc_js', 'kyc.wasm');
    const { wtns } = await snarkjs.wtns.calculate(input, wasmFile, undefined, console);
    console.log('  Witness generated OK');

    // 4. Generate proof
    console.log('\n[2/3] Generating Groth16 proof...');
    const zkeyFile = path.join(BUILD, 'kyc_0000.zkey');
    const start = Date.now();
    const { proof, publicSignals } = await snarkjs.groth16.prove(zkeyFile, wtns, console);
    const elapsed = Date.now() - start;
    console.log(`  Proof generated in ${elapsed}ms`);
    console.log(`  Public signals: ${JSON.stringify(publicSignals)}`);

    // 5. Verify proof
    console.log('\n[3/3] Verifying proof...');
    const vkFile = path.join(BUILD, 'verification_key.json');
    const vk = JSON.parse(readFileSync(vkFile, 'utf-8'));
    const valid = await snarkjs.groth16.verify(vk, publicSignals, proof, console);

    console.log('\n' + '='.repeat(55));
    if (valid) {
        console.log('  PROOF VALID - AlgoKYC Circom circuit working!');
        console.log('  Prove time: ' + elapsed + 'ms');
        console.log('  This is what runs in the USER\'S BROWSER');
    } else {
        console.log('  PROOF INVALID - check circuit/inputs');
    }
    console.log('='.repeat(55));

    if (!valid) process.exit(1);
}

main().catch(err => { console.error(err); process.exit(1); });

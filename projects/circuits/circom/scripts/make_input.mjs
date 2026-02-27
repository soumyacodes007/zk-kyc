/**
 * make_input.mjs — Generate test input.json for AlgoKYC circuit
 * Uses gnark cross-test values and computes nullifier + merkleRoot using MiMC
 */
import { MIMC_CONSTANTS, MIMC_ROUNDS, P } from '../test/mimc_constants.js';

const SMT_DEPTH = 20;

// ─── gnark-compatible MiMC (Miyaguchi-Preneel) ───────────────────────────────
function mimcEncrypt(m, k, constants) {
    let state = ((m + k) % P + P) % P;
    for (let i = 0; i < MIMC_ROUNDS; i++) {
        let t = (state + constants[i]) % P;
        // t^5 = t * t^2 * t^2
        let t2 = (t * t) % P;
        let t4 = (t2 * t2) % P;
        state = (t4 * t) % P;
    }
    return (state + k) % P;
}

function mimcHash(inputs) {
    let h = 0n;
    for (const m of inputs) {
        const mBig = BigInt(m);
        const r = mimcEncrypt(mBig, h, MIMC_CONSTANTS);
        // Miyaguchi-Preneel: h = encrypt(m, h) + h + m
        h = (r + h + mBig) % P;
    }
    return h;
}

// Test inputs
const aadhaarHash = 1234567890123456789012345678901234567890123456789n;
const walletSecret = 9876543210987654321098765432109876543210987654321n;
const appId = 756272073n;  // NullifierRegistry app ID
const dobYear = 2000n;
const currentYear = 2025n;

// Compute nullifier = MiMC-MP(aadhaarHash, appId, walletSecret)
const nullifier = mimcHash([aadhaarHash, appId, walletSecret]);
console.log(`nullifier  = ${nullifier}`);

// Compute SMT root for empty tree with nullifier at leftmost leaf position
// path = all zeros (left at every level), siblings = all zeros (empty tree)
let currentHash = nullifier;
for (let i = 0; i < SMT_DEPTH; i++) {
    // pos=0 → left child: parent = MiMC-MP(currentHash, sibling=0)
    currentHash = mimcHash([currentHash, 0n]);
}
const merkleRoot = currentHash;
console.log(`merkleRoot = ${merkleRoot}`);

// Build input object (all values as strings for JSON)
const input = {
    // Public inputs
    nullifier: nullifier.toString(),
    merkleRoot: merkleRoot.toString(),
    appId: appId.toString(),
    isIndian: "1",
    isAdult: "1",
    isKYCVerified: "1",

    // Private inputs
    aadhaarHash: aadhaarHash.toString(),
    walletSecret: walletSecret.toString(),
    dobYear: dobYear.toString(),
    currentYear: currentYear.toString(),
    nationalityIN: "1",
    kycStatus: "1",
    merkleSiblings: Array(SMT_DEPTH).fill("0"),
    merklePos: Array(SMT_DEPTH).fill("0"),

    // MiMC constants (110 values as strings)
    mimcConstants: MIMC_CONSTANTS.slice(0, MIMC_ROUNDS).map(c => c.toString()),
};

// Write to JSON
import { writeFileSync } from 'fs';
writeFileSync('build/input.json', JSON.stringify(input, null, 2));
console.log('\nWritten: build/input.json');
console.log(`MiMC constants: ${input.mimcConstants.length} values`);

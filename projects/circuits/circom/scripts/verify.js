/**
 * verify.js — AlgoKYC snarkjs PLONK proof verification (JS side)
 *
 * Verifies a PLONK proof against the verification key.
 * In production, verification happens ON-CHAIN via the AlgoPlonk LogicSig.
 * This script is for local testing only.
 *
 * Run: node scripts/verify.js
 */

import * as snarkjs from 'snarkjs';
import * as fs from 'fs';
import * as path from 'path';

const BUILD_DIR = path.join(import.meta.dirname, '../build');
const VK_FILE = path.join(BUILD_DIR, 'verification_key.json');
const PROOF_FILE = path.join(BUILD_DIR, 'test_proof.json');
const PUBSIG_FILE = path.join(BUILD_DIR, 'test_public.json');

async function verify() {
    console.log('=== AlgoKYC: snarkjs PLONK Proof Verification ===\n');

    if (!fs.existsSync(PROOF_FILE)) {
        console.error('❌ No proof found. Run: node scripts/prove.js first');
        process.exit(1);
    }

    const vk = JSON.parse(fs.readFileSync(VK_FILE, 'utf8'));
    const proof = JSON.parse(fs.readFileSync(PROOF_FILE, 'utf8'));
    const publicSignals = JSON.parse(fs.readFileSync(PUBSIG_FILE, 'utf8'));

    console.log('Verifying PLONK proof...');
    console.time('verify-time');

    const valid = await snarkjs.plonk.verify(vk, publicSignals, proof);

    console.timeEnd('verify-time');
    console.log(`\nResult: ${valid ? '✅ VALID' : '❌ INVALID'}\n`);

    if (valid) {
        console.log('Proof is valid — this would pass the on-chain LogicSig verifier.');
        console.log('Public signals verified on-chain:');
        console.log(`  nullifier:     ${publicSignals[0]}`);
        console.log(`  merkleRoot:    ${publicSignals[1]}`);
        console.log(`  appId:         ${publicSignals[2]}`);
        console.log(`  isIndian:      ${publicSignals[3]}`);
        console.log(`  isAdult:       ${publicSignals[4]}`);
        console.log(`  isKYCVerified: ${publicSignals[5]}`);
    } else {
        console.log('Proof is INVALID. Check inputs match circuit constraints.');
        process.exit(1);
    }
}

verify().catch(console.error);

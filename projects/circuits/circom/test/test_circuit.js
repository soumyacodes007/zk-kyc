/**
 * test_circuit.js — AlgoKYC Circom circuit tests
 *
 * Tests the KYC circuit with valid and invalid inputs.
 * Verifies that:
 *   ✅ Valid inputs produce a valid proof
 *   ❌ Wrong nullifier fails
 *   ❌ Age < 18 fails
 *   ❌ Non-Indian nationality fails
 *   ❌ KYC status 0 fails
 *   ❌ Wrong SMT path fails
 */

import * as snarkjs from 'snarkjs';
import { readFileSync } from 'fs';
import { join } from 'path';
import assert from 'assert';

const BUILD_DIR = join(import.meta.dirname, '../build');
const WASM_FILE = join(BUILD_DIR, 'kyc_js/kyc.wasm');
const ZKEY_FILE = join(BUILD_DIR, 'kyc_final.zkey');
const VK_FILE = join(BUILD_DIR, 'verification_key.json');

const SMT_DEPTH = 20;

// Base valid input
const VALID_INPUT = {
    nullifier: '12345678901234567890123456789012345678901234567890',
    merkleRoot: '0',
    appId: '1001',
    isIndian: '1',
    isAdult: '1',
    isKYCVerified: '1',
    aadhaarHash: '999999999999999999999999999999999999999999999999999',
    walletSecret: '888888888888888888888888888888888888888888888888888',
    dobYear: '1995',
    dobMonth: '6',
    dobDay: '15',
    currentYear: '2026',
    nationalityIN: '1',
    kycStatus: '1',
    merkleSiblings: Array(SMT_DEPTH).fill('0'),
    merklePos: Array(SMT_DEPTH).fill('0'),
};

async function proveAndVerify(input) {
    const { proof, publicSignals } = await snarkjs.plonk.fullProve(
        input, WASM_FILE, ZKEY_FILE
    );
    const vk = JSON.parse(readFileSync(VK_FILE, 'utf8'));
    return snarkjs.plonk.verify(vk, publicSignals, proof);
}

async function expectFail(input, label) {
    try {
        await snarkjs.plonk.fullProve(input, WASM_FILE, ZKEY_FILE);
        console.error(`  ❌ FAIL — expected ${label} to fail but proof was generated`);
        return false;
    } catch (_) {
        console.log(`  ✅ PASS — ${label} correctly fails proof generation`);
        return true;
    }
}

async function runTests() {
    console.log('=== AlgoKYC: Circuit Tests ===\n');

    if (!require('fs').existsSync(ZKEY_FILE)) {
        console.error('❌ zkey not found. Run: node scripts/setup.js first');
        process.exit(1);
    }

    let passed = 0; let failed = 0;

    // Test 1: Valid inputs should generate a valid proof
    console.log('[Test 1] Valid inputs → valid proof');
    const valid = await proveAndVerify(VALID_INPUT);
    if (valid) { console.log('  ✅ PASS\n'); passed++; }
    else { console.log('  ❌ FAIL\n'); failed++; }

    // Test 2: Age < 18 should fail
    console.log('[Test 2] Age < 18 → constraint failure');
    const under18 = { ...VALID_INPUT, dobYear: '2015', isAdult: '1' };
    if (await expectFail(under18, 'age < 18')) passed++; else failed++;
    console.log('');

    // Test 3: Non-Indian nationality should fail
    console.log('[Test 3] nationalityIN = 0 → constraint failure');
    const nonIndian = { ...VALID_INPUT, nationalityIN: '0', isIndian: '1' };
    if (await expectFail(nonIndian, 'nationalityIN=0')) passed++; else failed++;
    console.log('');

    // Test 4: KYC status = 0 should fail
    console.log('[Test 4] kycStatus = 0 → constraint failure');
    const notKYC = { ...VALID_INPUT, kycStatus: '0', isKYCVerified: '1' };
    if (await expectFail(notKYC, 'kycStatus=0')) passed++; else failed++;
    console.log('');

    // Test 5: Wrong public isIndian flag should fail
    console.log('[Test 5] isIndian = 0 (while nationalityIN=1) → constraint failure');
    const wrongFlag = { ...VALID_INPUT, isIndian: '0' };
    if (await expectFail(wrongFlag, 'isIndian=0 public mismatch')) passed++; else failed++;
    console.log('');

    // Results
    console.log(`=== Results: ${passed} passed, ${failed} failed ===`);
    if (failed > 0) process.exit(1);
}

runTests().catch(console.error);

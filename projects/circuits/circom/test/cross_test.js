/**
 * cross_test.js — gnark ↔ JS MiMC EXACT cross-test
 *
 * Uses the 110 MiMC constants dumped directly from gnark-crypto GetConstants()
 * (via `go run . dump-constants`) to guarantee byte-for-byte compatibility.
 *
 * Expected from `go test -run TestDumpVectors`:
 *   nullifier  = 8103393176036573007132872524834469807800761359628792454260082229404595316139
 *   merkleRoot = 6305893115142872804656369403988956436701953834697696250962592565123401843625
 */

import { MIMC_CONSTANTS, MIMC_ROUNDS, P } from './mimc_constants.js';
import { readFileSync } from 'fs';
import { join } from 'path';

const mod = a => ((a % P) + P) % P;

// ─── MiMC encrypt (gnark-crypto exact): (m+k+c[i])^5, 110 rounds, final +k ───
function mimcEncrypt(m, k) {
    let r = mod(m);
    for (let i = 0; i < MIMC_ROUNDS; i++) {
        const t = mod(r + k + MIMC_CONSTANTS[i]);
        const t2 = mod(t * t);
        const t4 = mod(t2 * t2);
        r = mod(t4 * t);            // t^5
    }
    return mod(r + k);
}

// ─── Miyaguchi-Preneel compression (exact gnark-crypto checksum) ───────────
// h starts at 0; for each input m: r = encrypt(m, key=h); h = r + h + m
function mimcHash(inputs) {
    let h = 0n;
    for (const m of inputs) {
        const r = mimcEncrypt(m, h);
        h = mod(r + h + m);
    }
    return h;
}

// ─── Cross-test ──────────────────────────────────────────────────────────────
async function runCrossTest() {
    console.log('=== AlgoKYC: gnark ↔ JS MiMC Cross-Test (Exact Constants) ===\n');

    // Load expected values from Go test output
    let expected;
    try {
        const vectorPath = join(import.meta.dirname, '../../gnark/output/test_vectors.json');
        const tv = JSON.parse(readFileSync(vectorPath, 'utf8'));
        expected = {
            aadhaarHash: BigInt(tv.aadhaarHash),
            appId: BigInt(tv.appId),
            walletSecret: BigInt(tv.walletSecret),
            nullifier: BigInt(tv.nullifier),
            merkleRoot: BigInt(tv.merkleRoot),
            smtDepth: tv.smtDepth,
            dobYear: BigInt(tv.dobYear),
            currentYear: BigInt(tv.currentYear),
        };
        console.log('✅ Loaded Go test vectors from output/test_vectors.json\n');
    } catch {
        expected = {
            aadhaarHash: 12345n,
            appId: 1001n,
            walletSecret: 67890n,
            nullifier: BigInt('8103393176036573007132872524834469807800761359628792454260082229404595316139'),
            merkleRoot: BigInt('6305893115142872804656369403988956436701953834697696250962592565123401843625'),
            smtDepth: 20,
            dobYear: 1995n,
            currentYear: 2026n,
        };
        console.log('ℹ️  Using hardcoded Go test vectors.\n');
    }

    let passed = 0, failed = 0;

    // ── Test 1: Nullifier ───────────────────────────────────────────────────────
    console.log('[Test 1] Nullifier = MiMC-MP(aadhaarHash, appId, walletSecret)');
    const computedNullifier = mimcHash([expected.aadhaarHash, expected.appId, expected.walletSecret]);

    if (computedNullifier === expected.nullifier) {
        console.log(`  ✅ PASS — gnark ↔ JS nullifiers match`);
        console.log(`         = ${computedNullifier}`);
        passed++;
    } else {
        console.log(`  ❌ FAIL`);
        console.log(`  Expected: ${expected.nullifier}`);
        console.log(`  Got:      ${computedNullifier}`);
        failed++;
    }
    console.log('');

    // ── Test 2: SMT root ───────────────────────────────────────────────────────
    console.log(`[Test 2] SMT root: walk ${expected.smtDepth} levels with all-zero siblings`);
    let currentHash = computedNullifier;
    for (let i = 0; i < expected.smtDepth; i++) {
        currentHash = mimcHash([currentHash, 0n]);
    }

    if (currentHash === expected.merkleRoot) {
        console.log(`  ✅ PASS — gnark ↔ JS SMT roots match`);
        console.log(`         = ${currentHash}`);
        passed++;
    } else {
        console.log(`  ❌ FAIL`);
        console.log(`  Expected: ${expected.merkleRoot}`);
        console.log(`  Got:      ${currentHash}`);
        failed++;
    }
    console.log('');

    // ── Test 3: Age >= 18 ──────────────────────────────────────────────────────
    console.log('[Test 3] Age >= 18');
    const age = expected.currentYear - expected.dobYear;
    if (age >= 18n) {
        console.log(`  ✅ PASS — age=${age}`);
        passed++;
    } else {
        console.log(`  ❌ FAIL — age=${age} < 18`);
        failed++;
    }
    console.log('');

    // ── Test 4: Invalid inputs should break ────────────────────────────────────
    console.log('[Test 4] Hash changes when inputs change (sanity check)');
    const wrongNullifier = mimcHash([expected.aadhaarHash + 1n, expected.appId, expected.walletSecret]);
    if (wrongNullifier !== expected.nullifier) {
        console.log('  ✅ PASS — different inputs → different hash');
        passed++;
    } else {
        console.log('  ❌ FAIL — hash collision!');
        failed++;
    }
    console.log('');

    // ── Summary ─────────────────────────────────────────────────────────────────
    console.log(`=== Results: ${passed} passed, ${failed} failed ===`);
    if (failed === 0) {
        console.log('\n✅ gnark ↔ JS MiMC fully consistent with exact constants.');
        console.log('   Browser SDK can use this mimcHash() directly.');
        console.log('   Circom circuit must import mimc_constants.js values via template.');
    } else {
        console.log('\n❌ Mismatch found. Check MiMC construction logic.');
        process.exit(1);
    }
}

runCrossTest().catch(console.error);

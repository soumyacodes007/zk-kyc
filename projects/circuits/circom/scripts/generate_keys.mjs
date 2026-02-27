/**
 * generate_keys.mjs — Generate proving key (zkey) and verification key for AlgoKYC
 * ===================================================================================
 * Generates a local Powers of Tau ceremony (test-grade, NOT for production),
 * then creates the Groth16 proving key and verification key for browser proving.
 *
 * For production:      use the Hermez Phase 1 trusted setup ptau file.
 * For testnet/dev:     this local ceremony is fine.
 *
 * Run: node scripts/generate_keys.mjs
 *
 * Outputs:
 *   build/pot15.ptau              — Powers of Tau (local ceremony)
 *   build/kyc_0000.zkey           — Groth16 proving key (circuit-specific)
 *   build/kyc_final.zkey          — Groth16 proving key (after contribution)
 *   build/verification_key.json   — Verification key (for off-chain/on-chain verify)
 */

import * as snarkjs from 'snarkjs';
import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(__dirname, '..', 'build');
const PTAU_FILE = path.join(BUILD, 'pot15.ptau');
const R1CS_FILE = path.join(BUILD, 'kyc.r1cs');
const ZKEY_0 = path.join(BUILD, 'kyc_0000.zkey');
const ZKEY_FINAL = path.join(BUILD, 'kyc_final.zkey');
const VK_FILE = path.join(BUILD, 'verification_key.json');

async function main() {
    console.log('=== AlgoKYC: Circom Trusted Setup ===\n');

    // 1. Check r1cs exists (compiled by circom)
    if (!existsSync(R1CS_FILE)) {
        throw new Error(`R1CS not found at ${R1CS_FILE}. Run: circom circuits/kyc.circom --r1cs --wasm --output build/ -l node_modules/`);
    }
    const r1csInfo = await snarkjs.r1cs.info(R1CS_FILE, console);
    console.log('');

    // 2. Powers of Tau — generate local test ceremony
    // Need at least 2^15 = 32768 constraints (circuit has 14,239 non-linear)
    // So power=15 is sufficient (supports 2^15 = 32768 constraints)
    if (!existsSync(PTAU_FILE)) {
        console.log('[1/4] Generating Powers of Tau (power=15, local ceremony)...');
        console.log('      This takes ~2-3 minutes...');

        // Phase 1: powers of tau
        const ptauTemp = path.join(BUILD, 'pot15_0000.ptau');
        await snarkjs.powersOfTau.newAccumulator(
            'bn128',
            15,   // 2^15 = 32768 constraints supported
            ptauTemp,
            console
        );

        // Contribute to Phase 1 (non-interactive, test only)
        const ptauTemp2 = path.join(BUILD, 'pot15_0001.ptau');
        await snarkjs.powersOfTau.contribute(
            ptauTemp,
            ptauTemp2,
            'AlgoKYC Test Contribution',
            'AlgoKYC entropy seed 2026',
            console
        );

        // Finalize Phase 1
        await snarkjs.powersOfTau.preparePhase2(ptauTemp2, PTAU_FILE, console);
        console.log(`\n  Written: ${PTAU_FILE}`);
    } else {
        console.log('[1/4] Powers of Tau already exists, skipping...');
    }

    // 3. Groth16 Phase 2 setup (circuit-specific)
    console.log('\n[2/4] Groth16 Phase 2 setup (kyc_0000.zkey)...');
    await snarkjs.zKey.newZKey(R1CS_FILE, PTAU_FILE, ZKEY_0, console);
    console.log(`  Written: ${ZKEY_0}`);

    // 4. Contribute to Phase 2 (non-interactive, test only)
    console.log('\n[3/4] Contributing to Phase 2 (kyc_final.zkey)...');
    await snarkjs.zKey.contribute(
        ZKEY_0,
        ZKEY_FINAL,
        'AlgoKYC Final Contribution',
        'AlgoKYC phase2 entropy 2026',
        console
    );
    console.log(`  Written: ${ZKEY_FINAL}`);

    // 5. Export verification key
    console.log('\n[4/4] Exporting verification key...');
    const vk = await snarkjs.zKey.exportVerificationKey(ZKEY_FINAL, console);
    const { writeFileSync } = await import('fs');
    writeFileSync(VK_FILE, JSON.stringify(vk, null, 2));
    console.log(`  Written: ${VK_FILE}`);

    console.log('\n' + '='.repeat(60));
    console.log('CIRCOM SETUP COMPLETE');
    console.log('='.repeat(60));
    console.log(`  R1CS:              ${R1CS_FILE}`);
    console.log(`  WASM:              ${BUILD}/kyc_js/kyc.wasm`);
    console.log(`  Proving key:       ${ZKEY_FINAL}`);
    console.log(`  Verification key:  ${VK_FILE}`);
    console.log('');
    console.log('  Next: run scripts/test_prove.mjs to generate a test proof');
    console.log('='.repeat(60));
}

main().catch(err => { console.error(err); process.exit(1); });

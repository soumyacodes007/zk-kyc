/**
 * setup.js — AlgoKYC Circom trusted setup
 *
 * Performs PLONK trusted setup using the Aztec Ignition powers-of-tau ceremony.
 * Downloads the universal SRS (powers_of_tau_15.ptau) and generates:
 *   - build/kyc_final.zkey   (proving key)
 *   - build/verification_key.json  (verifying key — for snarkjs.plonk.verify)
 *
 * Run: node scripts/setup.js
 * (Takes ~30-60 seconds on first run due to ptau download)
 */

import * as snarkjs from 'snarkjs';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

const BUILD_DIR = path.join(import.meta.dirname, '../build');
const PTAU_FILE = path.join(BUILD_DIR, 'powers_of_tau_15.ptau');
const R1CS_FILE = path.join(BUILD_DIR, 'kyc.r1cs');
const ZKEY_FILE = path.join(BUILD_DIR, 'kyc_final.zkey');
const VK_FILE = path.join(BUILD_DIR, 'verification_key.json');

async function setup() {
    console.log('=== AlgoKYC: Circom Trusted Setup ===\n');

    // Step 1: Compile Circom → R1CS + WASM
    console.log('[1/4] Compiling Circom circuit...');
    if (!fs.existsSync(BUILD_DIR)) fs.mkdirSync(BUILD_DIR, { recursive: true });

    execSync(
        `circom circuits/kyc.circom --r1cs --wasm --sym --output ${BUILD_DIR}`,
        { cwd: path.join(import.meta.dirname, '..'), stdio: 'inherit' }
    );
    console.log('      ✅ circuit compiled\n');

    // Step 2: Download ptau if not present
    // Using Hermez/Aztec ceremony ptau — valid for circuits up to 2^15 constraints
    if (!fs.existsSync(PTAU_FILE)) {
        console.log('[2/4] Downloading powers-of-tau (ptau15, ~50MB)...');
        const ptauUrl = 'https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_15.ptau';
        execSync(`curl -L -o ${PTAU_FILE} ${ptauUrl}`, { stdio: 'inherit' });
        console.log('      ✅ ptau downloaded\n');
    } else {
        console.log('[2/4] ptau already present ✅\n');
    }

    // Step 3: PLONK setup — generate zkey from r1cs + ptau
    console.log('[3/4] Running PLONK setup (generating zkey)...');
    await snarkjs.plonk.setup(R1CS_FILE, PTAU_FILE, ZKEY_FILE);
    console.log(`      ✅ zkey written to ${ZKEY_FILE}\n`);

    // Step 4: Export verification key
    console.log('[4/4] Exporting verification key...');
    const vk = await snarkjs.zKey.exportVerificationKey(ZKEY_FILE);
    fs.writeFileSync(VK_FILE, JSON.stringify(vk, null, 2));
    console.log(`      ✅ verification_key.json written to ${VK_FILE}\n`);

    console.log('=== Setup complete ===');
    console.log('Next: node scripts/prove.js    — generate a test proof');
}

setup().catch(console.error);

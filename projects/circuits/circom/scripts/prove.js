/**
 * prove.js — AlgoKYC snarkjs PLONK proof generation
 *
 * Generates a PLONK proof from a set of private inputs using the
 * compiled WASM + proving key from setup.js.
 *
 * In production, this logic runs entirely in the user's browser:
 *   - XML parser extracts inputs
 *   - prove() runs inside a Web Worker
 *   - Raw inputs deleted from memory after proof is generated
 *
 * Run: node scripts/prove.js
 */

import * as snarkjs from 'snarkjs';
import * as fs from 'fs';
import * as path from 'path';

const BUILD_DIR = path.join(import.meta.dirname, '../build');
const WASM_FILE = path.join(BUILD_DIR, 'kyc_js/kyc.wasm');
const ZKEY_FILE = path.join(BUILD_DIR, 'kyc_final.zkey');
const PROOF_FILE = path.join(BUILD_DIR, 'test_proof.json');
const PUBSIG_FILE = path.join(BUILD_DIR, 'test_public.json');

/**
 * Build the circuit input from Aadhaar XML parsed fields.
 * In the browser, `xmlFields` comes from the XML parser.
 * The SMT path comes from the backend's Merkle proof API.
 */
function buildInput(xmlFields, smtProof) {
    const SMT_DEPTH = 20;

    return {
        // Public inputs
        nullifier: xmlFields.nullifier,
        merkleRoot: smtProof.root,
        appId: xmlFields.appId,
        isIndian: '1',
        isAdult: '1',
        isKYCVerified: '1',

        // Private inputs
        aadhaarHash: xmlFields.aadhaarHash,
        walletSecret: xmlFields.walletSecret,
        dobYear: xmlFields.dobYear,
        dobMonth: xmlFields.dobMonth,
        dobDay: xmlFields.dobDay,
        currentYear: String(new Date().getFullYear()),
        nationalityIN: '1',
        kycStatus: '1',

        // SMT proof path (from backend)
        merkleSiblings: smtProof.siblings.map(String),
        merklePos: smtProof.positions.map(String),
    };
}

async function prove() {
    console.log('=== AlgoKYC: snarkjs PLONK Proof Generation ===\n');

    if (!fs.existsSync(ZKEY_FILE)) {
        console.error('❌ zkey not found. Run: node scripts/setup.js first');
        process.exit(1);
    }

    // Mock inputs for testing — real data from Aadhaar XML in production
    const mockInput = {
        // Public
        nullifier: '12345678901234567890123456789012345678901234567890',
        merkleRoot: '0',
        appId: '1001',
        isIndian: '1',
        isAdult: '1',
        isKYCVerified: '1',

        // Private
        aadhaarHash: '999999999999999999999999999999999999999999999999999',
        walletSecret: '888888888888888888888888888888888888888888888888888',
        dobYear: '1995',
        dobMonth: '6',
        dobDay: '15',
        currentYear: '2026',
        nationalityIN: '1',
        kycStatus: '1',

        // Empty SMT proof (all-zero siblings = valid for empty tree)
        merkleSiblings: Array(20).fill('0'),
        merklePos: Array(20).fill('0'),
    };

    console.log('[1/2] Generating PLONK proof (WASM)...');
    console.time('proof-time');

    const { proof, publicSignals } = await snarkjs.plonk.fullProve(
        mockInput,
        WASM_FILE,
        ZKEY_FILE
    );

    console.timeEnd('proof-time');
    console.log('      ✅ Proof generated\n');

    fs.writeFileSync(PROOF_FILE, JSON.stringify(proof, null, 2));
    fs.writeFileSync(PUBSIG_FILE, JSON.stringify(publicSignals, null, 2));

    console.log(`[2/2] Saved proof     → ${PROOF_FILE}`);
    console.log(`      Saved pubsignals → ${PUBSIG_FILE}\n`);

    console.log('Public signals (on-chain inputs):');
    console.log(`  nullifier:     ${publicSignals[0]}`);
    console.log(`  merkleRoot:    ${publicSignals[1]}`);
    console.log(`  appId:         ${publicSignals[2]}`);
    console.log(`  isIndian:      ${publicSignals[3]}`);
    console.log(`  isAdult:       ${publicSignals[4]}`);
    console.log(`  isKYCVerified: ${publicSignals[5]}`);

    console.log('\nNext: node scripts/verify.js — verify the proof locally');
}

prove().catch(console.error);

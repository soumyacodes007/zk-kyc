// debug_mimc.mjs — trace circuit computation step by step
import { MIMC_CONSTANTS, MIMC_ROUNDS, P } from '../test/mimc_constants.js';

const ROUNDS = 110;

// Exactly matching the Circom circuit's MiMCEncrypt template:
//   m_state[0] = m
//   t[i] = m_state[i] + k + c[i]
//   m_state[i+1] = t[i]^5
//   out = m_state[ROUNDS] + k
function mimcEncrypt(m, k, constants) {
    let state = m;  // m_state[0] = m  (NOT m+k!)
    for (let i = 0; i < ROUNDS; i++) {
        const t = (state + k + constants[i]) % P;  // m_state[i] + k + c[i]
        const t2 = (t * t) % P;
        const t4 = (t2 * t2) % P;
        state = (t4 * t) % P;  // t^5
    }
    return (state + k) % P;  // m_state[ROUNDS] + k
}

// Miyaguchi-Preneel: h = encrypt(m, h) + h + m
function mimcHash(inputs, constants) {
    let h = 0n;
    for (const m of inputs.map(BigInt)) {
        const r = mimcEncrypt(m, h, constants);
        h = (r + h + m) % P;
    }
    return h;
}

const aadhaarHash = 1234567890123456789012345678901234567890123456789n;
const walletSecret = 9876543210987654321098765432109876543210987654321n;
const appId = 756272073n;

const constants = MIMC_CONSTANTS.slice(0, 110);

const nullifier = mimcHash([aadhaarHash, appId, walletSecret], constants);
console.log(`nullifier  = ${nullifier}`);

let currentHash = nullifier;
for (let i = 0; i < 20; i++) {
    currentHash = mimcHash([currentHash, 0n], constants);
}
const merkleRoot = currentHash;
console.log(`merkleRoot = ${merkleRoot}`);

// Write fixed input.json
import { writeFileSync } from 'fs';
const input = {
    nullifier: nullifier.toString(),
    merkleRoot: merkleRoot.toString(),
    appId: appId.toString(),
    isIndian: "1",
    isAdult: "1",
    isKYCVerified: "1",
    aadhaarHash: aadhaarHash.toString(),
    walletSecret: walletSecret.toString(),
    dobYear: "2000",
    currentYear: "2025",
    nationalityIN: "1",
    kycStatus: "1",
    merkleSiblings: Array(20).fill("0"),
    merklePos: Array(20).fill("0"),
    mimcConstants: constants.map(c => c.toString()),
};
writeFileSync('build/input.json', JSON.stringify(input, null, 2));
console.log('\nWritten build/input.json');

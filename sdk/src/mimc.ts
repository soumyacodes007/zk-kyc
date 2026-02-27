/**
 * mimc.ts — gnark-compatible MiMC hash (BN254 field, 110 rounds, Miyaguchi-Preneel)
 * Matches exactly: gnark-crypto/ecc/bn254/fr/mimc and kyc.circom MiMCEncrypt template.
 *
 * Construction:
 *   encrypt(m, k): state=m; for i: state=(state+k+c[i])^5; return state+k
 *   hash(inputs): h=0; for m: r=encrypt(m,h), h=r+h+m  (Miyaguchi-Preneel)
 */

import { BN254_P, MIMC_CONSTANTS, MIMC_ROUNDS } from "./constants.js";

/**
 * Single MiMC block encryption — matches Circom MiMCEncrypt template exactly.
 * m_state[0] = m (NOT m+k), then each round: t = state + k + c[i], state = t^5
 */
function mimcEncrypt(m: bigint, k: bigint): bigint {
    let state = m; // m_state[0] = m
    for (let i = 0; i < MIMC_ROUNDS; i++) {
        const t = (state + k + MIMC_CONSTANTS[i]) % BN254_P;
        const t2 = (t * t) % BN254_P;
        const t4 = (t2 * t2) % BN254_P;
        state = (t4 * t) % BN254_P; // t^5
    }
    return (state + k) % BN254_P;
}

/**
 * MiMC hash of multiple field elements (Miyaguchi-Preneel)
 * h[0] = 0
 * h[i+1] = encrypt(inputs[i], h[i]) + h[i] + inputs[i]
 */
export function mimcHash(inputs: (bigint | string | number)[]): bigint {
    let h = 0n;
    for (const inp of inputs) {
        const m = BigInt(inp);
        const r = mimcEncrypt(m, h);
        h = (r + h + m) % BN254_P;
    }
    return h;
}

/**
 * Compute nullifier = MiMC-MP(aadhaarHash, appId, walletSecret)
 */
export function computeNullifier(
    aadhaarHash: bigint | string,
    appId: bigint | string | number,
    walletSecret: bigint | string
): bigint {
    return mimcHash([BigInt(aadhaarHash), BigInt(appId), BigInt(walletSecret)]);
}

/**
 * Compute SMT leaf → root for an empty tree (all siblings = 0)
 * Used for initial registration before any revocations.
 */
export function computeEmptyTreeRoot(nullifier: bigint, depth: number = 20): bigint {
    let h = nullifier;
    for (let i = 0; i < depth; i++) {
        h = mimcHash([h, 0n]);
    }
    return h;
}

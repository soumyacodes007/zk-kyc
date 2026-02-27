/**
 * verifier.ts — Off-chain ZK proof verification (issuer backend)
 * ===============================================================
 * The issuer backend calls verifyProof() to check the Groth16 proof
 * before registering the nullifier on-chain. This ensures:
 *   - Only valid ZK proofs result in on-chain registration
 *   - No private data (aadhaarHash, walletSecret) ever reaches the server
 *   - Double-registration prevented via nullifier uniqueness on NullifierRegistry
 */

import type { Groth16Proof, KYCPublicSignals } from "./types.js";

async function getSnarkjs() {
    return import("snarkjs");
}

export interface VerificationKey {
    protocol: string;
    curve: string;
    nPublic: number;
    vk_alpha_1: string[];
    vk_beta_2: string[][];
    vk_gamma_2: string[][];
    vk_delta_2: string[][];
    vk_alphabeta_12: string[][][];
    IC: string[][];
}

export interface VerifyResult {
    valid: boolean;
    /** Nullifier extracted from public signals (32-byte hex for Algorand) */
    nullifierHex?: string;
    /** All public signals if valid */
    publicSignals?: KYCPublicSignals;
    error?: string;
}

/**
 * Verify a Groth16 ZK proof against the AlgoKYC verification key.
 *
 * @param verificationKey - from build/verification_key.json
 * @param proof - Groth16Proof from the browser prover
 * @param publicSignals - [nullifier, merkleRoot, appId, isIndian, isAdult, isKYCVerified, ...constants]
 * @param expectedAppId - NullifierRegistry app ID (guard against cross-app attacks)
 */
export async function verifyProof(
    verificationKey: VerificationKey,
    proof: Groth16Proof,
    publicSignals: string[],
    expectedAppId?: number | string
): Promise<VerifyResult> {
    try {
        const snarkjs = await getSnarkjs();

        // snarkjs verification
        const valid = await (snarkjs as any).groth16.verify(
            verificationKey,
            publicSignals,
            proof
        );

        if (!valid) {
            return { valid: false, error: "Proof verification failed" };
        }

        // Extract and validate public signals
        const [nullifierStr, merkleRootStr, appIdStr, isIndian, isAdult, isKYCVerified] = publicSignals;

        // Sanity check claims
        if (isIndian !== "1") return { valid: false, error: "isIndian must be 1" };
        if (isAdult !== "1") return { valid: false, error: "isAdult must be 1" };
        if (isKYCVerified !== "1") return { valid: false, error: "isKYCVerified must be 1" };

        // Check appId matches if provided (prevents proof from one app being used for another)
        if (expectedAppId !== undefined && appIdStr !== expectedAppId.toString()) {
            return { valid: false, error: `appId mismatch: expected ${expectedAppId}, got ${appIdStr}` };
        }

        // Convert nullifier to 32-byte hex
        const nullifierHex = BigInt(nullifierStr).toString(16).padStart(64, "0");

        const signals: KYCPublicSignals = {
            nullifier: nullifierStr,
            merkleRoot: merkleRootStr,
            appId: appIdStr,
            isIndian: "1",
            isAdult: "1",
            isKYCVerified: "1",
        };

        return { valid: true, nullifierHex, publicSignals: signals };
    } catch (err) {
        return {
            valid: false,
            error: `Proof verification error: ${(err as Error).message}`,
        };
    }
}

/**
 * Load verification key from a URL (for use in backend/Node.js).
 * In the browser, import it directly as JSON.
 */
export async function loadVerificationKey(url: string): Promise<VerificationKey> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load verification key from ${url}: ${res.status}`);
    return res.json();
}

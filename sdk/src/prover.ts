/**
 * prover.ts — Browser-side ZK proof generation
 * =============================================
 * Runs entirely in the user's browser using snarkjs + compiled WASM.
 * Private inputs (aadhaarHash, walletSecret) NEVER leave the browser.
 *
 * Usage:
 *   const prover = new AlgoKYCProver({ wasmUrl, zkeyUrl });
 *   const result = await prover.generateProof({
 *     aadhaarHash, walletSecret, appId, dobYear, currentYear,
 *     merkleSiblings, merklePos
 *   });
 */

import { MIMC_CONSTANTS, MIMC_ROUNDS } from "./constants.js";
import { computeNullifier, computeEmptyTreeRoot, mimcHash } from "./mimc.js";
import type { KYCPrivateInputs, KYCProofResult, KYCPublicSignals, Groth16Proof } from "./types.js";

// Dynamic import of snarkjs (large lib, loaded on demand)
async function getSnarkjs() {
    // @ts-ignore — snarkjs has no great TS declarations
    return import("snarkjs");
}

export interface ProverOptions {
    /** URL to kyc.wasm (required) */
    wasmUrl: string;
    /** URL to kyc_final.zkey proving key (required) */
    zkeyUrl: string;
    /** SMT depth (default: 20) */
    smtDepth?: number;
}

export interface ProveInputs {
    /** SHA-256 of Aadhaar XML as BN254 field element (big decimal string) */
    aadhaarHash: string | bigint;
    /** User's random secret bound to their wallet (prevents proof reuse) */
    walletSecret: string | bigint;
    /** Algorand NullifierRegistry app ID */
    appId: string | number | bigint;
    /** Year of birth (e.g., 2000) */
    dobYear: number | string;
    /** Current year (e.g., 2025) */
    currentYear?: number | string;
    /** SMT sibling hashes (20 elements, use zeros for empty tree) */
    merkleSiblings?: string[];
    /** SMT path bits (20 elements, 0=left, 1=right) */
    merklePos?: string[];
}

export class AlgoKYCProver {
    private wasmUrl: string;
    private zkeyUrl: string;
    private smtDepth: number;

    constructor(options: ProverOptions) {
        this.wasmUrl = options.wasmUrl;
        this.zkeyUrl = options.zkeyUrl;
        this.smtDepth = options.smtDepth ?? 20;
    }

    /**
     * Generate a Groth16 ZK proof in the browser.
     * All computation happens locally — no private data is transmitted.
     *
     * @returns proof + public signals + nullifier hex + timing
     */
    async generateProof(inputs: ProveInputs): Promise<KYCProofResult> {
        const snarkjs = await getSnarkjs();

        const depth = this.smtDepth;
        const currentYear = inputs.currentYear ?? new Date().getFullYear();
        const siblings = inputs.merkleSiblings ?? Array(depth).fill("0");
        const pos = inputs.merklePos ?? Array(depth).fill("0");

        if (siblings.length !== depth || pos.length !== depth) {
            throw new Error(`merkleSiblings and merklePos must have ${depth} elements`);
        }

        // Compute nullifier and merkle root from private inputs
        const nullifier = computeNullifier(inputs.aadhaarHash, inputs.appId, inputs.walletSecret);
        const merkleRoot = this._computeMerkleRoot(nullifier, siblings, pos);

        // Build the circuit input object
        const circuitInput = {
            // Public signals
            nullifier: nullifier.toString(),
            merkleRoot: merkleRoot.toString(),
            appId: BigInt(inputs.appId).toString(),
            isIndian: "1",
            isAdult: "1",
            isKYCVerified: "1",

            // Private inputs
            aadhaarHash: BigInt(inputs.aadhaarHash).toString(),
            walletSecret: BigInt(inputs.walletSecret).toString(),
            dobYear: inputs.dobYear.toString(),
            currentYear: currentYear.toString(),
            nationalityIN: "1",
            kycStatus: "1",
            merkleSiblings: siblings,
            merklePos: pos,

            // MiMC constants (passed as circuit inputs for flexibility)
            mimcConstants: MIMC_CONSTANTS.slice(0, MIMC_ROUNDS).map(c => c.toString()),
        };

        // Fetch WASM and zkey
        const [wasmBuf, zkeyBuf] = await Promise.all([
            fetch(this.wasmUrl).then(r => r.arrayBuffer()),
            fetch(this.zkeyUrl).then(r => r.arrayBuffer()),
        ]);

        const start = performance.now();

        // Generate witness + proof entirely in browser
        const { proof, publicSignals } = await snarkjs.groth16.fullProve(
            circuitInput,
            new Uint8Array(wasmBuf),
            new Uint8Array(zkeyBuf)
        );

        const proveTimeMs = Math.round(performance.now() - start);

        const typedSignals: KYCPublicSignals = {
            nullifier: publicSignals[0],
            merkleRoot: publicSignals[1],
            appId: publicSignals[2],
            isIndian: "1",
            isAdult: "1",
            isKYCVerified: "1",
        };

        // Convert nullifier to 32-byte hex for Algorand
        const nullifierHex = nullifier.toString(16).padStart(64, "0");

        return {
            proof: proof as Groth16Proof,
            publicSignals: typedSignals,
            nullifierHex,
            proveTimeMs,
        };
    }

    /**
     * Compute the SMT root from nullifier + sibling path.
     * Mirrors the Circom circuit's SMT inclusion proof logic.
     */
    private _computeMerkleRoot(
        nullifier: bigint,
        siblings: string[],
        pos: string[]
    ): bigint {
        let current = nullifier;
        for (let i = 0; i < siblings.length; i++) {
            const sibling = BigInt(siblings[i]);
            const p = Number(pos[i]);
            // pos=0 → current is left: hash(current, sibling)
            // pos=1 → current is right: hash(sibling, current)
            current = p === 0
                ? mimcHash([current, sibling])
                : mimcHash([sibling, current]);
        }
        return current;
    }
}

/**
 * Convenience: compute just the nullifier without generating a full proof.
 * Useful for checking if an address is already registered.
 */
export function computeNullifierHex(
    aadhaarHash: string | bigint,
    appId: string | number | bigint,
    walletSecret: string | bigint
): string {
    const n = computeNullifier(aadhaarHash, appId, walletSecret);
    return n.toString(16).padStart(64, "0");
}

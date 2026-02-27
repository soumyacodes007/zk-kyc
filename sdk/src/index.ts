/**
 * index.ts — AlgoKYC SDK Public API
 * ===================================
 * @algokyc/sdk — Zero-Knowledge KYC for Algorand
 *
 * Usage:
 *   import { AlgoKYCProver, AlgoKYCClient, verifyProof } from "@algokyc/sdk";
 *
 * Browser flow (user side):
 *   const prover = new AlgoKYCProver({ wasmUrl, zkeyUrl });
 *   const { proof, publicSignals, nullifierHex } = await prover.generateProof({
 *     aadhaarHash, walletSecret, appId: 756272073, dobYear: 2000
 *   });
 *   // Send proof + publicSignals to your issuer backend
 *
 * Backend flow (issuer side):
 *   const result = await verifyProof(verificationKey, proof, publicSignals, 756272073);
 *   if (result.valid) {
 *     const client = new AlgoKYCClient();
 *     const txid = await client.registerNullifier(issuerAccount, result.nullifierHex!, userWallet);
 *   }
 *
 * dApp flow (any app checking KYC):
 *   const client = new AlgoKYCClient();
 *   const status = await client.verifyKYC(userWalletAddress);
 *   if (status.isVerified) { ... allow access ... }
 */

// ── Core classes ─────────────────────────────────────────────────────────────
export { AlgoKYCProver, computeNullifierHex } from "./prover.js";
export type { ProverOptions, ProveInputs } from "./prover.js";

export { AlgoKYCClient } from "./algorand.js";

export { verifyProof, loadVerificationKey } from "./verifier.js";
export type { VerifyResult, VerificationKey } from "./verifier.js";

// ── Crypto primitives ─────────────────────────────────────────────────────────
export { mimcHash, computeNullifier, computeEmptyTreeRoot } from "./mimc.js";

// ── Constants ─────────────────────────────────────────────────────────────────
export { MIMC_CONSTANTS, MIMC_ROUNDS, BN254_P } from "./constants.js";

// ── Types ─────────────────────────────────────────────────────────────────────
export {
    DEFAULT_CONTRACT_IDS,
} from "./types.js";

export type {
    KYCPublicSignals,
    Groth16Proof,
    KYCPrivateInputs,
    KYCProofResult,
    KYCStatus,
    AlgoKYCConfig,
    ContractIds,
} from "./types.js";

// ── Version ───────────────────────────────────────────────────────────────────
export const SDK_VERSION = "0.1.0";
export const NETWORK = "testnet";
export const DEPLOYED_AT = "2026-02-27";

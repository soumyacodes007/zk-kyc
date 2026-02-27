/**
 * types.ts — AlgoKYC SDK Types
 */

/** Public signals output from the ZK circuit */
export interface KYCPublicSignals {
    nullifier: string;       // BN254 field element as decimal string
    merkleRoot: string;      // SMT root
    appId: string;           // Algorand app ID (NullifierRegistry)
    isIndian: "1";           // always 1 — circuit enforces
    isAdult: "1";            // always 1 — circuit enforces (age >= 18)
    isKYCVerified: "1";      // always 1 — circuit enforces
}

/** Groth16 proof structure (snarkjs format) */
export interface Groth16Proof {
    pi_a: [string, string, string];
    pi_b: [[string, string], [string, string], [string, string]];
    pi_c: [string, string, string];
    protocol: "groth16";
    curve: "bn128";
}

/** Private inputs — NEVER leave the browser */
export interface KYCPrivateInputs {
    aadhaarHash: string;       // SHA-256 of Aadhaar XML as field element
    walletSecret: string;      // user's random secret (ties proof to wallet)
    dobYear: string;           // year of birth (e.g., "2000")
    currentYear: string;       // current year (e.g., "2025")
    nationalityIN: "1";        // must be 1 (Indian)
    kycStatus: "1";            // must be 1 (verified)
    merkleSiblings: string[];  // SMT sibling nodes (20 elements)
    merklePos: string[];       // SMT path bits 0/1 (20 elements)
}

/** Full proof output from generateProof() */
export interface KYCProofResult {
    proof: Groth16Proof;
    publicSignals: KYCPublicSignals;
    nullifierHex: string;    // nullifier as 32-byte hex (for on-chain use)
    proveTimeMs: number;
}

/** KYC status returned by verifyKYC() */
export interface KYCStatus {
    isVerified: boolean;
    nullifier?: string;        // registered nullifier if verified
    totalRegistered?: number;  // total credentials in registry
    appId: number;
}

/** SDK configuration */
export interface AlgoKYCConfig {
    /** Algod API endpoint (default: testnet AlgoNode) */
    algodServer?: string;
    /** Algod API token (empty for public AlgoNode) */
    algodToken?: string;
    /** Override deployed contract IDs */
    contractIds?: Partial<typeof DEFAULT_CONTRACT_IDS>;
    /** Path/URL to kyc.wasm (default: bundled) */
    wasmUrl?: string;
    /** Path/URL to kyc_final.zkey (default: bundled) */
    zkeyUrl?: string;
}

/** Deployed contract IDs on Algorand Testnet */
export const DEFAULT_CONTRACT_IDS = {
    nullifierRegistry: 756272073,
    smtRegistry: 756272075,
    kycBoxStorage: 756272299,
    credentialManager: 756281076,
    credentialAsaId: 756281102,
} as const;

export type ContractIds = typeof DEFAULT_CONTRACT_IDS;

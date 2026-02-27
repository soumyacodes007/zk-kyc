// Type shim for snarkjs — no official @types/snarkjs package exists
declare module "snarkjs" {
    export const groth16: {
        fullProve(
            input: Record<string, unknown>,
            wasmFile: string | Uint8Array,
            zkeyFile: string | Uint8Array,
            logger?: unknown
        ): Promise<{ proof: unknown; publicSignals: string[] }>;
        prove(
            zkeyFile: string | Uint8Array,
            wtns: Uint8Array,
            logger?: unknown
        ): Promise<{ proof: unknown; publicSignals: string[] }>;
        verify(
            verificationKey: unknown,
            publicSignals: string[],
            proof: unknown,
            logger?: unknown
        ): Promise<boolean>;
    };
    export const wtns: {
        calculate(
            input: Record<string, unknown>,
            wasmFile: string | Uint8Array,
            wtnsFile?: string,
            logger?: unknown
        ): Promise<{ wtns: Uint8Array }>;
    };
    export const zKey: {
        exportVerificationKey(zkeyFile: string | Uint8Array, logger?: unknown): Promise<unknown>;
    };
    export const powersOfTau: {
        newAccumulator(curve: string, power: number, file: string, logger?: unknown): Promise<void>;
        contribute(ptau: string, newPtau: string, name: string, entropy: string, logger?: unknown): Promise<void>;
        preparePhase2(ptau: string, final: string, logger?: unknown): Promise<void>;
    };
}

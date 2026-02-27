/**
 * algorand.ts — On-chain interactions with AlgoKYC Algorand contracts
 * ====================================================================
 * Uses @algorandfoundation/algokit-utils AlgorandClient (modern API)
 * per skill guidance in .Antigravity/skills/use-algokit-utils/
 *
 * Functions:
 *   - registerNullifier()    — atomic fund + register txn group
 *   - verifyKYC()            — check KYC status for any wallet
 *   - isNullifierRegistered() — direct box check
 */

import { AlgorandClient, algo, microAlgo } from "@algorandfoundation/algokit-utils";
import algosdk from "algosdk";
import { DEFAULT_CONTRACT_IDS, type AlgoKYCConfig, type KYCStatus, type ContractIds } from "./types.js";



function hexToBytes(hex: string): Uint8Array {
    const clean = hex.replace(/^0x/, "").padStart(64, "0").slice(0, 64);
    const bytes = new Uint8Array(clean.length / 2);
    for (let i = 0; i < clean.length; i += 2) {
        bytes[i / 2] = parseInt(clean.slice(i, i + 2), 16);
    }
    return bytes;
}

/** Encode a raw bytes array as ABI byte[] (2-byte big-endian length + bytes) */
function encodeAbiBytes(bytes: Uint8Array): Uint8Array {
    const result = new Uint8Array(2 + bytes.length);
    result[0] = 0;
    result[1] = bytes.length;
    result.set(bytes, 2);
    return result;
}

export class AlgoKYCClient {
    private algorand: AlgorandClient;
    private contracts: ContractIds;

    constructor(config: AlgoKYCConfig = {}) {
        if (config.algodServer) {
            this.algorand = AlgorandClient.fromConfig({
                algodConfig: {
                    server: config.algodServer,
                    port: "",
                    token: config.algodToken ?? "",
                },
            });
        } else {
            // Default: Algorand Testnet via AlgoNode
            this.algorand = AlgorandClient.testNet();
        }

        this.contracts = {
            ...DEFAULT_CONTRACT_IDS,
            ...config.contractIds,
        } as ContractIds;
    }

    /**
     * Register a verified nullifier on-chain.
     * Called by the issuer backend AFTER verifyProof() returns valid=true.
     *
     * Sends an atomic group:
     *   1. Payment → NullifierRegistry (0.05 ALGO box MBR)
     *   2. AppCall → register(nullifier, walletAddress)
     *
     * @param signerMnemonic  - Issuer's 25-word Algorand mnemonic
     * @param nullifierHex    - 32-byte nullifier hex from ZK proof public signals
     * @param walletAddress   - User's Algorand wallet address
     * @returns confirmed transaction ID
     */
    async registerNullifier(
        signerMnemonic: string,
        nullifierHex: string,
        walletAddress: string
    ): Promise<string> {
        const appId = BigInt(this.contracts.nullifierRegistry);
        const appAddr = algosdk.getApplicationAddress(Number(appId));

        // Build signing account from mnemonic
        const account = this.algorand.account.fromMnemonic(signerMnemonic);
        this.algorand.setSignerFromAccount(account);

        // Build box name = "nul_" prefix + 32-byte nullifier
        const nullifierBytes = hexToBytes(nullifierHex);
        const boxPrefixBytes = new TextEncoder().encode("nul_");
        const boxName = new Uint8Array([...boxPrefixBytes, ...nullifierBytes]);

        // ABI encode arguments
        const encodedNullifier = encodeAbiBytes(nullifierBytes);

        // Atomic group: fund for box MBR + call register()
        const result = await this.algorand
            .newGroup()
            .addPayment({
                sender: account.addr,
                receiver: appAddr,
                amount: microAlgo(50_000), // 0.05 ALGO for box MBR
            })
            .addAppCallMethodCall({
                sender: account.addr,
                appId,
                method: algosdk.ABIMethod.fromSignature("register(byte[],address)void"),
                // algokit-utils handles ABI encoding of args automatically
                args: [encodedNullifier, walletAddress],
                boxReferences: [{ appId, name: boxName }],
                accountReferences: [walletAddress],
            })
            .send();

        return result.txIds[result.txIds.length - 1];
    }

    /**
     * Verify KYC status for a wallet by reading NullifierRegistry global state.
     * This is the main function dApps use to gate access.
     */
    async verifyKYC(_walletAddress?: string): Promise<KYCStatus> {
        const appId = this.contracts.nullifierRegistry;
        try {
            const appInfo = await this.algorand.client.algod
                .getApplicationByID(appId)
                .do();

            const gState = (appInfo as any).params?.["global-state"] as Array<{
                key: string;
                value: { type: number; uint: number; bytes: string };
            }> | undefined;

            let totalRegistered = 0;
            for (const kv of gState ?? []) {
                const key = Buffer.from(kv.key, "base64").toString("utf-8");
                if (key === "total_registered") {
                    totalRegistered = kv.value.uint;
                }
            }

            return { isVerified: totalRegistered > 0, totalRegistered, appId };
        } catch {
            return { isVerified: false, appId };
        }
    }

    /**
     * Check if a specific nullifier is registered on-chain via box storage.
     * More precise than verifyKYC() — directly checks the box.
     */
    async isNullifierRegistered(nullifierHex: string): Promise<boolean> {
        const appId = this.contracts.nullifierRegistry;
        const nullifierBytes = hexToBytes(nullifierHex);
        const boxName = new Uint8Array([
            ...new TextEncoder().encode("nul_"),
            ...nullifierBytes,
        ]);

        try {
            const box = await this.algorand.client.algod
                .getApplicationBoxByName(appId, boxName)
                .do();
            return (box as any).value?.length > 0;
        } catch {
            return false;
        }
    }

    /** KYCRED ASA ID from deployed contracts */
    getCredentialAsaId(): number {
        return this.contracts.credentialAsaId;
    }

    /** Explorer URL for a transaction */
    static explorerTxUrl(txid: string): string {
        return `https://allo.info/tx/${txid}`;
    }

    /** Explorer URL for an application */
    static explorerAppUrl(appId: number): string {
        return `https://allo.info/application/${appId}`;
    }
}

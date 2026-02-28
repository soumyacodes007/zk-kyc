"""
zk_verifier.py — Off-chain ZK Proof Verification (Groth16 via snarkjs CLI)
===========================================================================
The issuer backend calls verify_proof() before registering any nullifier.
This is a pure Python wrapper around the snarkjs CLI — no native bindings needed.

In production, you'd call the snarkjs Node.js module via subprocess, or write
a tiny Node.js microservice. For V1 we use a subprocess call to snarkjs CLI.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Path to the snarkjs CLI (relative to circom dir)
CIRCOM_DIR = Path(__file__).parent.parent / "projects/circuits/circom"
SNARKJS_CLI = CIRCOM_DIR / "node_modules/snarkjs/cli.js"


class ProofVerifyResult(NamedTuple):
    valid: bool
    nullifier_int: int | None
    nullifier_hex: str | None
    merkle_root: str | None
    app_id: int | None
    is_indian: bool
    is_adult: bool
    is_kyc_verified: bool
    error: str | None


def verify_groth16_proof(
    verification_key_path: str | Path,
    public_signals: list[str],
    proof: dict,
    expected_app_id: int | None = None,
) -> ProofVerifyResult:
    """
    Verify a Groth16 ZK proof using snarkjs CLI.

    Args:
        verification_key_path: Path to verification_key.json
        public_signals: List of public signal strings from the prover
        proof:          Groth16 proof dict (pi_a, pi_b, pi_c, protocol, curve)
        expected_app_id: NullifierRegistry app ID — rejects if mismatch

    Returns:
        ProofVerifyResult with valid flag and extracted signals
    """
    vk_path = Path(verification_key_path)
    if not vk_path.exists():
        return ProofVerifyResult(
            valid=False, nullifier_int=None, nullifier_hex=None,
            merkle_root=None, app_id=None,
            is_indian=False, is_adult=False, is_kyc_verified=False,
            error=f"Verification key not found: {vk_path}",
        )

    # Write proof and public signals to temp files for snarkjs
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        proof_path  = Path(tmpdir) / "proof.json"
        public_path = Path(tmpdir) / "public.json"

        proof_path.write_text(json.dumps(proof))
        public_path.write_text(json.dumps(public_signals))

        try:
            result = subprocess.run(
                ["node", str(SNARKJS_CLI), "groth16", "verify",
                 str(vk_path), str(public_path), str(proof_path)],
                capture_output=True, text=True,
                cwd=str(CIRCOM_DIR), timeout=30
            )
            output = result.stdout + result.stderr
            logger.debug(f"snarkjs output: {output.strip()}")

            if result.returncode != 0 or "OK!" not in output:
                return ProofVerifyResult(
                    valid=False, nullifier_int=None, nullifier_hex=None,
                    merkle_root=None, app_id=None,
                    is_indian=False, is_adult=False, is_kyc_verified=False,
                    error=f"snarkjs verification failed: {output.strip()}",
                )

        except subprocess.TimeoutExpired:
            return ProofVerifyResult(
                valid=False, nullifier_int=None, nullifier_hex=None,
                merkle_root=None, app_id=None,
                is_indian=False, is_adult=False, is_kyc_verified=False,
                error="Proof verification timed out",
            )
        except FileNotFoundError:
            return ProofVerifyResult(
                valid=False, nullifier_int=None, nullifier_hex=None,
                merkle_root=None, app_id=None,
                is_indian=False, is_adult=False, is_kyc_verified=False,
                error="snarkjs CLI not found — run: cd projects/circuits/circom && npm install",
            )

    # Parse public signals
    # Order: [nullifier, merkleRoot, appId, isIndian, isAdult, isKYCVerified, ...mimcConstants]
    if len(public_signals) < 6:
        return ProofVerifyResult(
            valid=False, nullifier_int=None, nullifier_hex=None,
            merkle_root=None, app_id=None,
            is_indian=False, is_adult=False, is_kyc_verified=False,
            error=f"Expected ≥6 public signals, got {len(public_signals)}",
        )

    nullifier_int    = int(public_signals[0])
    merkle_root      = public_signals[1]
    app_id           = int(public_signals[2])
    is_indian        = public_signals[3] == "1"
    is_adult         = public_signals[4] == "1"
    is_kyc_verified  = public_signals[5] == "1"

    # Validate claim flags
    if not (is_indian and is_adult and is_kyc_verified):
        return ProofVerifyResult(
            valid=False, nullifier_int=nullifier_int, nullifier_hex=None,
            merkle_root=merkle_root, app_id=app_id,
            is_indian=is_indian, is_adult=is_adult, is_kyc_verified=is_kyc_verified,
            error="KYC claims not satisfied (must be Indian adult with KYC status)",
        )

    # Validate appId binding (prevents proof from one dApp being used for another)
    if expected_app_id is not None and app_id != expected_app_id:
        return ProofVerifyResult(
            valid=False, nullifier_int=nullifier_int, nullifier_hex=None,
            merkle_root=merkle_root, app_id=app_id,
            is_indian=is_indian, is_adult=is_adult, is_kyc_verified=is_kyc_verified,
            error=f"appId mismatch: proof bound to {app_id}, expected {expected_app_id}",
        )

    # Convert nullifier to 32-byte hex for Algorand box key
    nullifier_hex = hex(nullifier_int)[2:].zfill(64)

    return ProofVerifyResult(
        valid=True,
        nullifier_int=nullifier_int,
        nullifier_hex=nullifier_hex,
        merkle_root=merkle_root,
        app_id=app_id,
        is_indian=is_indian,
        is_adult=is_adult,
        is_kyc_verified=is_kyc_verified,
        error=None,
    )

"""
config.py — Backend settings (Pydantic v2 Settings)
Reads from .env file automatically.
"""
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Algorand
    algod_server: str = "https://testnet-api.algonode.cloud"
    algod_token: str = ""
    deployer_mnemonic: str

    # Deployed contract IDs (Algorand Testnet)
    nullifier_registry_id: int = 756272073
    smt_registry_id: int = 756272075
    kyc_box_storage_id: int = 756272299
    credential_manager_id: int = 756281076
    credential_asa_id: int = 756281102

    # ZK
    verification_key_path: str = "../projects/circuits/circom/build/verification_key.json"

    # Security
    api_secret_key: str = "algokyc-dev-secret-change-in-production"

    # ECIES issuer private key (secp256k1, 32 bytes hex)
    issuer_private_key_hex: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()

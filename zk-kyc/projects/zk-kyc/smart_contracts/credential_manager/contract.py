"""
CredentialManager — AlgoKYC v1
Issues and manages non-transferable KYC credential ASAs.

Deployment flow:
  1. deploy_create()         → bare create, sets issuer
  2. fund app with 0.3 ALGO  → for ASA creation MBR
  3. initialize_asa()        → creates the KYCRED ASA, returns ASA ID
"""
from algopy import ARC4Contract, Account, Asset, Bytes, Global, Txn, UInt64, arc4, itxn


class CredentialManager(ARC4Contract):
    """Issues and revokes non-transferable KYC credential ASAs."""

    def __init__(self) -> None:
        self.issuer = Account()
        self.credential_asa_id = UInt64(0)
        self.total_issued = UInt64(0)
        self.total_revoked = UInt64(0)

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Initialize — deployer becomes issuer. Fund app with 0.3 ALGO then call initialize_asa()."""
        self.issuer = Txn.sender
        self.total_issued = UInt64(0)
        self.total_revoked = UInt64(0)

    @arc4.abimethod()
    def initialize_asa(self) -> UInt64:
        """
        Create the KYC credential ASA. Must be called AFTER funding app with >= 0.3 ALGO.
        Returns the new ASA ID. App address is manager/clawback/freeze.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        assert self.credential_asa_id == UInt64(0), "ASA already created"

        result = itxn.AssetConfig(
            total=1_000_000_000,
            decimals=0,
            default_frozen=True,
            unit_name=b"KYCRED",
            asset_name=b"AlgoKYC Credential",
            url=b"https://algokyc.dev",
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            freeze=Global.current_application_address,
            reserve=Global.current_application_address,
            fee=0,
        ).submit()

        self.credential_asa_id = result.created_asset.id
        return result.created_asset.id

    @arc4.abimethod()
    def issue_credential(self, recipient: Account, nullifier: Bytes) -> None:
        """Issue a KYC credential to a verified wallet. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"

        asa = Asset(self.credential_asa_id)

        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=False,
            fee=0,
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=asa,
            asset_receiver=recipient,
            asset_amount=1,
            note=nullifier,
            fee=0,
        ).submit()

        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=True,
            fee=0,
        ).submit()

        self.total_issued += UInt64(1)

    @arc4.abimethod()
    def revoke_credential(self, wallet: Account, nullifier: Bytes) -> None:
        """Revoke credential via clawback. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"

        itxn.AssetTransfer(
            xfer_asset=Asset(self.credential_asa_id),
            asset_sender=wallet,
            asset_receiver=Global.current_application_address,
            asset_amount=1,
            note=nullifier,
            fee=0,
        ).submit()

        self.total_revoked += UInt64(1)

    @arc4.abimethod(readonly=True)
    def get_credential_asa_id(self) -> UInt64:
        """Return the credential ASA ID."""
        return self.credential_asa_id

    @arc4.abimethod(readonly=True)
    def get_total_issued(self) -> UInt64:
        return self.total_issued

    @arc4.abimethod(readonly=True)
    def get_total_revoked(self) -> UInt64:
        return self.total_revoked

    @arc4.abimethod()
    def update_issuer(self, new_issuer: Account) -> None:
        """Transfer issuer role. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"
        self.issuer = new_issuer

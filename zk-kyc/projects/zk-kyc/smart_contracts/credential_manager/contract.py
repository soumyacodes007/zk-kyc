"""
CredentialManager — AlgoKYC v1
Issues and manages non-transferable KYC credential ASAs.

Non-transferability enforced via:
  - default_frozen=True
  - clawback = app address (issuer controls via inner txns)
  - freeze  = app address

Issue flow:  unfreeze wallet → transfer 1 unit → re-freeze
Revoke flow: clawback 1 unit from wallet

Skills compliance:
  - fee=0 on all inner txns (fee pooling)
  - result.created_asset.id from AssetConfig result
  - Global.current_application_address as clawback/freeze/manager
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
    def create(self) -> UInt64:
        """
        Initialize contract and create the KYC credential ASA.
        Returns new ASA ID. App address becomes clawback/freeze/manager.
        Fund this contract with ≥ 0.2 ALGO before calling (for ASA creation MBR).
        """
        self.issuer = Txn.sender
        self.total_issued = UInt64(0)
        self.total_revoked = UInt64(0)

        # Create non-transferable credential ASA
        # App address is manager/clawback/freeze so only this contract can operate it
        result = itxn.AssetConfig(
            total=1_000_000_000,
            decimals=0,
            default_frozen=True,                              # frozen by default
            unit_name=b"KYCRED",
            asset_name=b"AlgoKYC Credential",
            url=b"https://algokyc.dev",
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            freeze=Global.current_application_address,
            reserve=Global.current_application_address,
            fee=0,                                            # fee pooling
        ).submit()

        self.credential_asa_id = result.created_asset.id
        return result.created_asset.id

    @arc4.abimethod()
    def issue_credential(self, recipient: Account, nullifier: Bytes) -> None:
        """
        Issue a KYC credential to a verified wallet. Issuer-only.
        Recipient MUST have opted into credential ASA before this call.
        Flow: unfreeze → transfer 1 unit → re-freeze (non-transferable).
        Nullifier stored in note field for on-chain auditability.
        """
        assert Txn.sender == self.issuer, "Only issuer"

        asa = Asset(self.credential_asa_id)

        # Step 1: Unfreeze so recipient can receive
        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=False,
            fee=0,
        ).submit()

        # Step 2: Transfer 1 credential unit (nullifier in note for audit)
        itxn.AssetTransfer(
            xfer_asset=asa,
            asset_receiver=recipient,
            asset_amount=1,
            note=nullifier,
            fee=0,
        ).submit()

        # Step 3: Re-freeze — non-transferable
        itxn.AssetFreeze(
            freeze_asset=asa,
            freeze_account=recipient,
            frozen=True,
            fee=0,
        ).submit()

        self.total_issued += UInt64(1)

    @arc4.abimethod()
    def revoke_credential(self, wallet: Account, nullifier: Bytes) -> None:
        """
        Revoke credential via clawback. Issuer-only.
        Called on: fraud detection, Aadhaar cancel, court order, expiry.
        """
        assert Txn.sender == self.issuer, "Only issuer"

        itxn.AssetTransfer(
            xfer_asset=Asset(self.credential_asa_id),
            asset_sender=wallet,                              # clawback source
            asset_receiver=Global.current_application_address,  # return to app
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
        """Total credentials issued."""
        return self.total_issued

    @arc4.abimethod(readonly=True)
    def get_total_revoked(self) -> UInt64:
        """Total credentials revoked."""
        return self.total_revoked

    @arc4.abimethod()
    def update_issuer(self, new_issuer: Account) -> None:
        """Transfer issuer role. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"
        self.issuer = new_issuer

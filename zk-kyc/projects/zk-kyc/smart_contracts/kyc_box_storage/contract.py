"""
KYCBoxStorage — AlgoKYC v1
ECIES-encrypted identity blobs in Algorand box storage.
BoxMap: nullifier (Bytes) → encrypted_blob (Bytes).
Only issuer private key can decrypt. No PII on-chain.
"""
from algopy import ARC4Contract, Account, BoxMap, Bytes, Txn, UInt64, arc4


class KYCBoxStorage(ARC4Contract):
    """Box storage for ECIES-encrypted identity blobs keyed by nullifier."""

    def __init__(self) -> None:
        self.issuer = Account()
        self.total_blobs = UInt64(0)
        # BoxMap: nullifier → encrypted_blob (~300-500 bytes of ECIES ciphertext)
        self.blobs = BoxMap(Bytes, Bytes, key_prefix=b"blob_")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Initialize — deployer becomes issuer."""
        self.issuer = Txn.sender
        self.total_blobs = UInt64(0)

    @arc4.abimethod()
    def store_blob(self, nullifier: Bytes, encrypted_blob: Bytes) -> None:
        """
        Store ECIES-encrypted identity blob. Issuer-only.
        encrypted_blob = ECIES.encrypt(identity, issuer_public_key)
        Generated in user's browser — zero PII transmitted to contract.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        is_new = nullifier not in self.blobs
        self.blobs[nullifier] = encrypted_blob
        if is_new:
            self.total_blobs += UInt64(1)

    @arc4.abimethod()
    def get_blob(self, nullifier: Bytes) -> Bytes:
        """
        Retrieve encrypted blob. Issuer-only.
        Backend decrypts with reconstructed Shamir issuer key during court order.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        assert nullifier in self.blobs, "Blob not found"
        return self.blobs[nullifier]

    @arc4.abimethod()
    def delete_blob(self, nullifier: Bytes) -> None:
        """
        Delete identity blob (DPDP Right to Erasure). Issuer-only.
        Called on full credential revocation.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        assert nullifier in self.blobs, "Blob not found"
        del self.blobs[nullifier]
        if self.total_blobs > UInt64(0):
            self.total_blobs -= UInt64(1)

    @arc4.abimethod(readonly=True)
    def has_blob(self, nullifier: Bytes) -> bool:
        """Check whether an encrypted blob exists for this nullifier."""
        return nullifier in self.blobs

    @arc4.abimethod(readonly=True)
    def get_total_blobs(self) -> UInt64:
        """Total encrypted blobs currently stored."""
        return self.total_blobs

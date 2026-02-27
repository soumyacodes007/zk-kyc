"""
NullifierRegistry — AlgoKYC v1
Maps nullifier_hash → wallet_address. Sybil prevention.
Uses BoxMap: key=nullifier(Bytes/32), value=Account address(Bytes/32).
"""
from algopy import ARC4Contract, Account, BoxMap, Bytes, Txn, UInt64, arc4


class NullifierRegistry(ARC4Contract):
    """Registry mapping nullifier_hash → wallet for Sybil prevention."""

    def __init__(self) -> None:
        # Issuer is set at creation — only issuer can register/invalidate
        self.issuer = Account()
        self.total_registered = UInt64(0)
        # BoxMap: nullifier (Bytes) → wallet address (Bytes 32)
        # key_prefix keeps boxes namespaced
        self.nullifiers = BoxMap(Bytes, Bytes, key_prefix=b"nul_")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Initialize — caller becomes the issuer."""
        self.issuer = Txn.sender
        self.total_registered = UInt64(0)

    @arc4.abimethod()
    def register(self, nullifier: Bytes, wallet: Account) -> None:
        """
        Register nullifier → wallet. Issuer-only.
        Fails if nullifier already registered (one Aadhaar per wallet).
        """
        assert Txn.sender == self.issuer, "Only issuer"
        assert nullifier not in self.nullifiers, "Nullifier already registered"
        self.nullifiers[nullifier] = wallet.bytes
        self.total_registered += UInt64(1)

    @arc4.abimethod(readonly=True)
    def is_registered(self, nullifier: Bytes) -> bool:
        """Check if a nullifier has been registered."""
        return nullifier in self.nullifiers

    @arc4.abimethod(readonly=True)
    def get_wallet(self, nullifier: Bytes) -> Bytes:
        """Retrieve wallet bytes for a nullifier (court order lookup)."""
        assert nullifier in self.nullifiers, "Nullifier not found"
        return self.nullifiers[nullifier]

    @arc4.abimethod()
    def invalidate(self, nullifier: Bytes) -> None:
        """Remove nullifier registration — issuer-only, used on revocation."""
        assert Txn.sender == self.issuer, "Only issuer"
        assert nullifier in self.nullifiers, "Nullifier not found"
        del self.nullifiers[nullifier]
        if self.total_registered > UInt64(0):
            self.total_registered -= UInt64(1)

    @arc4.abimethod(readonly=True)
    def get_total_registered(self) -> UInt64:
        """Total registered credentials."""
        return self.total_registered

    @arc4.abimethod()
    def update_issuer(self, new_issuer: Account) -> None:
        """Transfer issuer role. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"
        self.issuer = new_issuer

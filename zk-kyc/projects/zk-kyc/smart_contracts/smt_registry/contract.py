"""
SMTRegistry — AlgoKYC v1
Stores on-chain root of the Sparse Merkle Tree of valid nullifiers.
Single GlobalState Bytes — O(1) update per issuance/revocation.
"""
from algopy import ARC4Contract, Account, Bytes, Global, Txn, UInt64, arc4


class SMTRegistry(ARC4Contract):
    """On-chain store for the Sparse Merkle Tree root."""

    def __init__(self) -> None:
        self.issuer = Account()
        # SMT root — 32 bytes (Poseidon hash of the full tree)
        self.smt_root = Bytes()
        self.last_updated_round = UInt64(0)
        self.update_count = UInt64(0)

    @arc4.abimethod(create="require")
    def create(self, initial_root: Bytes) -> None:
        """Initialize with the genesis SMT root (32 zero bytes = empty tree)."""
        self.issuer = Txn.sender
        self.smt_root = initial_root
        self.last_updated_round = Global.round
        self.update_count = UInt64(0)

    @arc4.abimethod()
    def update_root(self, new_root: Bytes) -> None:
        """
        Update SMT root. Issuer-only.
        Called after every credential issuance or revocation.
        1 Algorand tx = all revocations reflected immediately.
        """
        assert Txn.sender == self.issuer, "Only issuer"
        self.smt_root = new_root
        self.last_updated_round = Global.round
        self.update_count += UInt64(1)

    @arc4.abimethod(readonly=True)
    def get_root(self) -> Bytes:
        """Return current SMT root for client-side SMT inclusion proof verification."""
        return self.smt_root

    @arc4.abimethod(readonly=True)
    def get_last_updated_round(self) -> UInt64:
        """Algorand round at which root was last updated."""
        return self.last_updated_round

    @arc4.abimethod(readonly=True)
    def get_update_count(self) -> UInt64:
        """Total root updates (audit counter)."""
        return self.update_count

    @arc4.abimethod()
    def update_issuer(self, new_issuer: Account) -> None:
        """Transfer issuer role. Issuer-only."""
        assert Txn.sender == self.issuer, "Only issuer"
        self.issuer = new_issuer

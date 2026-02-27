"""
Integration tests for NullifierRegistry contract.
Uses algorand-python-testing for unit-style tests.
"""
import pytest
from algopy import Bytes, UInt64
from algopy.testing import AlgopyTestContext, arc4_prefix, context_stack


@pytest.fixture()
def ctx() -> AlgopyTestContext:
    with context_stack.open(AlgopyTestContext()) as c:
        yield c


class TestNullifierRegistry:

    def test_create_sets_issuer(self, ctx: AlgopyTestContext) -> None:
        """Creating the contract sets the caller as issuer."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        assert contract.issuer == ctx.default_sender

    def test_register_nullifier(self, ctx: AlgopyTestContext) -> None:
        """Issuer can register a nullifier → wallet mapping."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        nullifier = Bytes(b"\x01" * 32)
        wallet = ctx.any.account()
        contract.register(nullifier, wallet)

        assert contract.is_registered(nullifier) is True
        assert contract.total_registered == UInt64(1)

    def test_get_wallet_returns_correct_address(self, ctx: AlgopyTestContext) -> None:
        """get_wallet returns the wallet bytes stored during register."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        nullifier = Bytes(b"\x02" * 32)
        wallet = ctx.any.account()
        contract.register(nullifier, wallet)

        stored = contract.get_wallet(nullifier)
        assert stored == wallet.bytes

    def test_register_duplicate_fails(self, ctx: AlgopyTestContext) -> None:
        """Registering the same nullifier twice should fail (Sybil prevention)."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        nullifier = Bytes(b"\x03" * 32)
        wallet1 = ctx.any.account()
        contract.register(nullifier, wallet1)

        with pytest.raises(Exception, match="Nullifier already registered"):
            wallet2 = ctx.any.account()
            contract.register(nullifier, wallet2)

    def test_non_issuer_register_fails(self, ctx: AlgopyTestContext) -> None:
        """Only the issuer can register nullifiers."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        intruder = ctx.any.account()
        with ctx.txn.create(sender=intruder):
            with pytest.raises(Exception, match="Only issuer"):
                contract.register(Bytes(b"\x04" * 32), intruder)

    def test_invalidate_removes_registration(self, ctx: AlgopyTestContext) -> None:
        """Invalidate removes the nullifier; is_registered returns False."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        nullifier = Bytes(b"\x05" * 32)
        wallet = ctx.any.account()
        contract.register(nullifier, wallet)
        contract.invalidate(nullifier)

        assert contract.is_registered(nullifier) is False
        assert contract.total_registered == UInt64(0)

    def test_update_issuer(self, ctx: AlgopyTestContext) -> None:
        """Issuer can transfer the issuer role to a new account."""
        from smart_contracts.nullifier_registry.contract import NullifierRegistry

        contract = NullifierRegistry()
        contract.create()

        new_issuer = ctx.any.account()
        contract.update_issuer(new_issuer)
        assert contract.issuer == new_issuer


class TestSMTRegistry:

    def test_create_sets_initial_root(self, ctx: AlgopyTestContext) -> None:
        """Create sets genesis root and initializes counters."""
        from smart_contracts.smt_registry.contract import SMTRegistry

        genesis_root = Bytes(b"\x00" * 32)
        contract = SMTRegistry()
        contract.create(genesis_root)

        assert contract.get_root() == genesis_root
        assert contract.get_update_count() == UInt64(0)

    def test_update_root(self, ctx: AlgopyTestContext) -> None:
        """Issuer can update the SMT root and counter increments."""
        from smart_contracts.smt_registry.contract import SMTRegistry

        contract = SMTRegistry()
        contract.create(Bytes(b"\x00" * 32))

        new_root = Bytes(b"\xab" * 32)
        contract.update_root(new_root)

        assert contract.get_root() == new_root
        assert contract.get_update_count() == UInt64(1)

    def test_non_issuer_update_root_fails(self, ctx: AlgopyTestContext) -> None:
        """Only issuer can update the SMT root."""
        from smart_contracts.smt_registry.contract import SMTRegistry

        contract = SMTRegistry()
        contract.create(Bytes(b"\x00" * 32))

        intruder = ctx.any.account()
        with ctx.txn.create(sender=intruder):
            with pytest.raises(Exception, match="Only issuer"):
                contract.update_root(Bytes(b"\xff" * 32))


class TestKYCBoxStorage:

    def test_store_and_retrieve_blob(self, ctx: AlgopyTestContext) -> None:
        """Issuer can store and retrieve an encrypted blob."""
        from smart_contracts.kyc_box_storage.contract import KYCBoxStorage

        contract = KYCBoxStorage()
        contract.create()

        nullifier = Bytes(b"\x01" * 32)
        encrypted_blob = Bytes(b"ECIES_CIPHERTEXT_PLACEHOLDER_300_BYTES")
        contract.store_blob(nullifier, encrypted_blob)

        assert contract.has_blob(nullifier) is True
        assert contract.get_total_blobs() == UInt64(1)
        assert contract.get_blob(nullifier) == encrypted_blob

    def test_duplicate_store_overwrites(self, ctx: AlgopyTestContext) -> None:
        """Storing a blob for an existing nullifier overwrites it without incrementing count."""
        from smart_contracts.kyc_box_storage.contract import KYCBoxStorage

        contract = KYCBoxStorage()
        contract.create()

        nullifier = Bytes(b"\x02" * 32)
        blob1 = Bytes(b"FIRST_BLOB")
        blob2 = Bytes(b"SECOND_BLOB_UPDATED")

        contract.store_blob(nullifier, blob1)
        contract.store_blob(nullifier, blob2)  # overwrite

        # Count should still be 1
        assert contract.get_total_blobs() == UInt64(1)
        assert contract.get_blob(nullifier) == blob2

    def test_delete_blob(self, ctx: AlgopyTestContext) -> None:
        """Deleting a blob removes it and decrements total count."""
        from smart_contracts.kyc_box_storage.contract import KYCBoxStorage

        contract = KYCBoxStorage()
        contract.create()

        nullifier = Bytes(b"\x03" * 32)
        contract.store_blob(nullifier, Bytes(b"SOME_CIPHERTEXT"))
        contract.delete_blob(nullifier)

        assert contract.has_blob(nullifier) is False
        assert contract.get_total_blobs() == UInt64(0)

    def test_non_issuer_store_fails(self, ctx: AlgopyTestContext) -> None:
        """Non-issuer cannot store blobs."""
        from smart_contracts.kyc_box_storage.contract import KYCBoxStorage

        contract = KYCBoxStorage()
        contract.create()

        intruder = ctx.any.account()
        with ctx.txn.create(sender=intruder):
            with pytest.raises(Exception, match="Only issuer"):
                contract.store_blob(Bytes(b"\x04" * 32), Bytes(b"EVIL_BLOB"))

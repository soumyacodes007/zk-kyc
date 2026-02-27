"""Deploy config for SMTRegistry."""
import logging

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    from smart_contracts.artifacts.smt_registry.smt_registry_client import (
        SMTRegistryFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    factory = algorand.client.get_typed_app_factory(
        SMTRegistryFactory, default_sender=deployer.address
    )

    # Genesis SMT root = 32 zero bytes (empty Sparse Merkle Tree)
    GENESIS_ROOT = b"\x00" * 32

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount(algo=1),
                sender=deployer.address,
                receiver=app_client.app_address,
            )
        )

    logger.info(
        f"SMTRegistry deployed: app_id={app_client.app_id}, address={app_client.app_address}"
    )

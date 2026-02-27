"""Deploy config for CredentialManager."""
import logging

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    from smart_contracts.artifacts.credential_manager.credential_manager_client import (
        CredentialManagerFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    factory = algorand.client.get_typed_app_factory(
        CredentialManagerFactory, default_sender=deployer.address
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        # Fund contract to cover ASA creation MBR (0.1 ALGO) + inner txns
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount(algo=2),
                sender=deployer.address,
                receiver=app_client.app_address,
            )
        )

    logger.info(
        f"CredentialManager deployed: app_id={app_client.app_id}, "
        f"address={app_client.app_address}"
    )

"""Deploy config for KYCBoxStorage."""
import logging

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    from smart_contracts.artifacts.kyc_box_storage.kyc_box_storage_client import (
        KYCBoxStorageFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    factory = algorand.client.get_typed_app_factory(
        KYCBoxStorageFactory, default_sender=deployer.address
    )

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
                amount=algokit_utils.AlgoAmount(algo=3),  # Box storage needs MBR funding
                sender=deployer.address,
                receiver=app_client.app_address,
            )
        )

    logger.info(
        f"KYCBoxStorage deployed: app_id={app_client.app_id}, address={app_client.app_address}"
    )

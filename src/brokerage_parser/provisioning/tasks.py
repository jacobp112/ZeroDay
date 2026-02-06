import logging
import uuid
from celery import shared_task
from brokerage_parser.db import SessionLocal
from brokerage_parser.provisioning.workflow import ProvisioningWorkflow

logger = logging.getLogger(__name__)

@shared_task(name="provision_tenant_task")
def provision_tenant_task(request_id: str):
    """
    Async task to provision a tenant.
    """
    session = SessionLocal()
    try:
        workflow = ProvisioningWorkflow(session)
        success = workflow.provision_tenant(uuid.UUID(request_id))

        if success:
            logger.info(f"Provisioning task succeeded for request {request_id}")
        else:
            logger.error(f"Provisioning task failed or returned false for request {request_id}")

    except Exception as e:
        logger.exception(f"Provisioning task crashed for request {request_id}")
    finally:
        session.close()

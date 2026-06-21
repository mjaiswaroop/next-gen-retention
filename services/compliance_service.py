import logging
import uuid
from datetime import datetime

logger = logging.getLogger("retention_core.compliance")

def erase_customer(tenant_id: int, customer_id: str, requested_by: int) -> dict:
    """Mock erasure logic."""
    logger.info(f"Erasing customer {customer_id} for tenant {tenant_id}")
    return {
        "status": "success",
        "message": "Customer data erased successfully.",
        "certificate_id": str(uuid.uuid4()),
        "erased_at": datetime.utcnow().isoformat()
    }

import logging
import uuid
import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from brokerage_parser.db import SessionLocal
from brokerage_parser.models.metering import UsageEvent, UsageEventType
from brokerage_parser.config import settings

logger = logging.getLogger(__name__)

class UsageCollector:
    """
    Collects usage events for metering.
    Designed to be used within API endpoints and Workers.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def record_event(
        self,
        tenant_id: uuid.UUID,
        event_type: UsageEventType,
        quantity: float = 1.0,
        resource_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime.datetime] = None
    ) -> None:
        """
        Records a usage event.
        If a DB session is provided in init, uses it (and assumes transaction management).
        If not, creates a new session and commits immediately.
        """
        if not timestamp:
            timestamp = datetime.datetime.now(datetime.timezone.utc)

        event = UsageEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            quantity=quantity,
            resource_id=resource_id,
            metadata=metadata or {},
            timestamp=timestamp
        )

        should_close = False
        if self.db:
            session = self.db
        else:
            session = SessionLocal()
            should_close = True

        try:
            session.add(event)
            if should_close:
                session.commit()
            else:
                session.flush() # Flush to get ID if needed, but let caller commit
        except Exception as e:
            logger.error(f"Failed to record usage event: {e}")
            if should_close:
                session.rollback()
        finally:
            if should_close:
                session.close()

        # Metrics (Safe)
        try:
            from brokerage_parser.monitoring.metrics import USAGE_EVENTS
            USAGE_EVENTS.labels(
                tenant_id=str(tenant_id),
                event_type=event_type.value
            ).inc()
        except:
            pass

    def get_unaggregated_events(self, limit: int = 1000):
        """
        Fetch events that haven't been aggregated yet.
        """
        # This method might be better in a repository or task logic.
        pass

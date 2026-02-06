import logging
from datetime import datetime
from sqlalchemy import func, select
from celery import shared_task

from brokerage_parser.db import SessionLocal
from brokerage_parser.models.metering import UsageEvent, UsageRecord, UsageEventType
from brokerage_parser.config import settings

logger = logging.getLogger(__name__)

@shared_task(name="aggregate_daily_usage")
def aggregate_daily_usage():
    """
    Aggregates un-aggregated usage events into daily records.
    """
    session = SessionLocal()
    try:
        # locking? Or just atomic update?
        # Simple approach: Fetch unaggregated, group by (tenant, date, type), upsert, then mark aggregated.
        # Handling large volume: chunking.

        limit = 1000
        while True:
            # 1. Fetch unaggregated events
            events = session.query(UsageEvent).filter(
                UsageEvent.aggregated_at.is_(None)
            ).limit(limit).all()

            if not events:
                break

            # 2. Group in memory (simpler for now, or use SQL group by)
            # We use memory map: (tenant_id, date) -> {jobs: 0, api: 0, storage: 0, compute: 0}
            updates = {}
            event_ids = []

            for event in events:
                date_key = event.timestamp.date()
                key = (event.tenant_id, date_key)

                if key not in updates:
                     updates[key] = {
                         "jobs": 0, "api": 0, "storage": 0, "compute": 0
                     }

                q = float(event.quantity)

                if event.event_type == UsageEventType.JOB_SUBMITTED:
                    updates[key]["jobs"] += int(q)
                elif event.event_type == UsageEventType.API_CALL:
                    updates[key]["api"] += int(q)
                elif event.event_type == UsageEventType.STORAGE_USED:
                    # Input is MB, Storage Bytes is Bytes (BigInt)
                    updates[key]["storage"] += int(q * 1024 * 1024)
                elif event.event_type == UsageEventType.COMPUTE_SECONDS:
                    updates[key]["compute"] += q

                event_ids.append(event.event_id)

            # 3. Upsert Records
            for (tenant_id, date_val), counts in updates.items():
                # Check exist
                record = session.query(UsageRecord).filter(
                    UsageRecord.tenant_id == tenant_id,
                    UsageRecord.date == date_val
                ).with_for_update().first()

                if not record:
                    record = UsageRecord(
                        tenant_id=tenant_id,
                        date=date_val,
                        jobs_count=0, api_calls_count=0, storage_bytes=0, compute_seconds=0
                    )
                    session.add(record)

                record.jobs_count += counts["jobs"]
                record.api_calls_count += counts["api"]
                record.storage_bytes += counts["storage"]
                record.compute_seconds += counts["compute"]

            # 4. Mark aggregated
            now = datetime.utcnow()
            session.query(UsageEvent).filter(
                UsageEvent.event_id.in_(event_ids)
            ).update({"aggregated_at": now}, synchronize_session=False)

            session.commit()

            if len(events) < limit:
                break

        logger.info("Aggregation completed")

    except Exception as e:
        logger.error(f"Aggregation failed: {e}")
        session.rollback()
    finally:
        session.close()

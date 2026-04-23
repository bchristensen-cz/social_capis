from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from google.cloud import bigquery

from .hashing import ensure_email_hash, ensure_phone_hash
from .models import Conversion
from .observability import get_logger

log = get_logger(__name__)

_SQL = """
SELECT
  event_time,
  event_name,
  email_hash,
  phone_hash,
  value,
  currency,
  order_id
FROM `{project}.{dataset}.{table}`
WHERE DATE(event_time) = @target_date
  AND order_id IS NOT NULL
  AND (email_hash IS NOT NULL OR phone_hash IS NOT NULL)
ORDER BY event_time ASC
"""


def resolve_target_date(override: str = "") -> date:
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return (datetime.now(UTC) - timedelta(days=1)).date()


def fetch(
    project: str,
    dataset: str,
    table: str,
    target: date,
    client: bigquery.Client | None = None,
) -> list[Conversion]:
    bq = client or bigquery.Client(project=project)
    sql = _SQL.format(project=project, dataset=dataset, table=table)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("target_date", "DATE", target)],
        labels={"job": "social-capis-daily"},
    )
    log.info("bq_query_start", extra={"target_date": target.isoformat()})
    job = bq.query(sql, job_config=job_config)
    rows = list(job.result())
    log.info("bq_query_done", extra={"target_date": target.isoformat(), "row_count": len(rows)})
    return [_row_to_conversion(r) for r in rows]


def _row_to_conversion(row) -> Conversion:
    et = row["event_time"]
    if isinstance(et, datetime) and et.tzinfo is None:
        et = et.replace(tzinfo=UTC)
    return Conversion(
        event_time=et,
        event_name=str(row["event_name"]),
        email_hash=ensure_email_hash(row["email_hash"]),
        phone_hash=ensure_phone_hash(row["phone_hash"]),
        value=float(row["value"] or 0),
        currency=str(row["currency"] or "USD"),
        order_id=str(row["order_id"]),
    )


def rows_to_jsonl_bytes(rows: Iterable[Conversion]) -> bytes:
    import json

    lines = []
    for r in rows:
        lines.append(
            json.dumps(
                {
                    "event_time": r.event_time.isoformat(),
                    "event_name": r.event_name,
                    "email_hash": r.email_hash,
                    "phone_hash": r.phone_hash,
                    "value": r.value,
                    "currency": r.currency,
                    "order_id": r.order_id,
                },
                separators=(",", ":"),
            )
        )
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")

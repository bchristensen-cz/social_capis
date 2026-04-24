from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from google.cloud import bigquery

from .hashing import ensure_email_hash, ensure_phone_hash
from .models import Conversion
from .observability import get_logger

log = get_logger(__name__)

BUSINESS_TZ = ZoneInfo("America/Denver")
EVENT_NAME = "Purchase"

# Cafe Zupas CAPI source: matched customers from in-store POS, non-digital
# (digital orders already post CAPI events directly from checkout), no catering,
# excluding the test store. `BusinessDate` is the POS-day partition column.
_SQL = """
WITH capi_data AS (
  SELECT
    oc.brink_order_id AS transaction_id,
    oc.netsales AS transaction_value,
    'USD' AS currency,
    oc.mapped_email AS email,
    oc.order_datetime AS event_time,
    CONCAT('1', i.Phone) AS phone_raw
  FROM `{project}.{dataset}.OrderCustomer` oc
  LEFT JOIN `{project}.{dataset}.cust_info` i
    ON i.mapped_cust_id = oc.mapped_cust_id
  WHERE oc.BusinessDate = @target_date
    AND oc.mapped_email IS NOT NULL
    AND oc.pulse_order_id IS NULL
    AND oc.iscatering = 0
    AND oc.storeid <> 1111
)
SELECT
  event_time,
  transaction_id,
  transaction_value,
  currency,
  email,
  phone_raw
FROM capi_data
WHERE transaction_id IS NOT NULL
ORDER BY event_time ASC
"""


def _yesterday_denver() -> date:
    now = datetime.now(BUSINESS_TZ)
    return date.fromordinal(now.toordinal() - 1)


def resolve_target_date(override: str = "") -> date:
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return _yesterday_denver()


def fetch(
    project: str,
    dataset: str,
    target: date,
    client: bigquery.Client | None = None,
) -> list[Conversion]:
    bq = client or bigquery.Client(project=project)
    sql = _SQL.format(project=project, dataset=dataset)
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
        event_name=EVENT_NAME,
        email_hash=ensure_email_hash(row["email"]),
        phone_hash=ensure_phone_hash(row["phone_raw"]),
        value=float(row["transaction_value"] or 0),
        currency=str(row["currency"] or "USD"),
        order_id=str(row["transaction_id"]),
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

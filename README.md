# social_capis

Daily offline conversions pipeline: pulls yesterday's purchases from BigQuery, posts them to TikTok, Meta, and Snapchat Conversions APIs, and commits a dated audit snapshot back to this repo.

Runs as a **Cloud Run Job** triggered by **Cloud Scheduler** at 04:00 America/Denver.

## Architecture

```
Cloud Scheduler (0 4 * * * MT)
        ↓ OIDC
Cloud Run Job  ──→  BigQuery (yesterday's partition)
                 ──→  TikTok / Meta / Snapchat CAPIs
                 ──→  GitHub Contents API (data/YYYY-MM-DD.jsonl + failures/)
GitHub push → Cloud Build trigger → Artifact Registry → `gcloud run jobs update`
```

## Local development

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
# or: .venv/bin/pip install -r requirements-dev.txt  # Linux/Mac

# Run tests + lint
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check .
```

## Local dry run

`DRY_RUN=true` skips the GitHub commit and uses test-event codes for the three ad platforms.

```bash
gcloud auth application-default login

export GCP_PROJECT=marketing-data-442316
export BQ_DATASET=sales_ops           # default
export GITHUB_REPO=bchristensen-cz/social_capis
export GITHUB_PAT=...
export TIKTOK_ACCESS_TOKEN=...
export TIKTOK_PIXEL_CODE=...
export META_ACCESS_TOKEN=...
export META_DATASET_ID=...
export SNAP_ACCESS_TOKEN=...
export SNAP_PIXEL_ID=...
export DRY_RUN=true

python -m src.main
```

Optional:
- `TARGET_DATE=2026-04-22` — backfill a specific date (idempotent, safe to re-run).
- `ENABLE_TIKTOK=false` / `ENABLE_META=false` / `ENABLE_SNAP=false` — disable a single platform.
- `ERROR_RATE_THRESHOLD=0.05` — non-zero exit threshold (default 5%).

## Data source

The job reads from two tables in `sales_ops`, joined and filtered inside [src/bigquery_source.py](src/bigquery_source.py):

- `OrderCustomer` — POS transactions with `brink_order_id`, `netsales`, `mapped_email`, `order_datetime`, `BusinessDate`, `pulse_order_id`, `iscatering`, `storeid`
- `cust_info` — customer table with `mapped_cust_id` → `Phone`

Row-level filters (applied in SQL):
- `BusinessDate = yesterday` (America/Denver)
- `mapped_email IS NOT NULL` (requires loyalty/in-store scan match)
- `pulse_order_id IS NULL` (digital orders already CAPI-posted at checkout)
- `iscatering = 0`
- `storeid <> 1111` (test store)

All rows are sent as `Purchase` events. Phone numbers are validated with the `phonenumbers` library (Google libphonenumber) — invalid numbers are dropped from the payload while the row is still sent with just the email. Both email and phone are SHA-256 hashed in the job, never in SQL.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (or no rows found) |
| 1 | Unhandled exception |
| 2 | All platforms disabled |
| 3 | At least one platform 100% failing |
| 4 | Total error rate above `ERROR_RATE_THRESHOLD` |

## Deployment

See the implementation plan at `C:\Users\bchristensen\.claude\plans\title-plan-for-synchronous-hinton.md` for the full MVP deployment checklist (gcloud commands, IAM bindings, Scheduler setup).

CI/CD: push to `main` triggers Cloud Build, which rebuilds the image and runs `gcloud run jobs update social-capis-daily`. GitHub Actions handles lint + tests only.

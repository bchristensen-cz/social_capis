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

export GCP_PROJECT=your-project
export BQ_DATASET=your_dataset
export BQ_TABLE=your_table
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

## Expected BigQuery schema

| Column | Type | Notes |
|---|---|---|
| `event_time` | TIMESTAMP | Partition column |
| `event_name` | STRING | e.g. `Purchase` |
| `email_hash` | STRING | SHA-256 hex (raw values also accepted — re-hashed locally) |
| `phone_hash` | STRING | SHA-256 hex of E.164 digits-only |
| `value` | NUMERIC | |
| `currency` | STRING | ISO 4217 |
| `order_id` | STRING | Unique; used for `event_id = sha256(order_id + "|" + platform)` |

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

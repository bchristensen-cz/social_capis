from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from . import bigquery_source, github_commit
from .config import Config
from .models import Conversion, SendResult
from .observability import configure_logging, get_logger
from .platforms.base import PlatformClient
from .platforms.meta import MetaClient
from .platforms.snapchat import SnapchatClient
from .platforms.tiktok import TikTokClient

log = get_logger(__name__)


def build_clients(cfg: Config) -> list[PlatformClient]:
    clients: list[PlatformClient] = []
    test_code = cfg.test_event_code or ("TEST" if cfg.dry_run else "")
    if cfg.enable_tiktok:
        clients.append(
            TikTokClient(cfg.tiktok_access_token, cfg.tiktok_pixel_code, test_code)
        )
    if cfg.enable_meta:
        clients.append(
            MetaClient(cfg.meta_access_token, cfg.meta_dataset_id, test_code)
        )
    if cfg.enable_snap:
        clients.append(
            SnapchatClient(cfg.snap_access_token, cfg.snap_pixel_id, test_code)
        )
    return clients


def send_to_all(
    clients: Sequence[PlatformClient], conversions: Sequence[Conversion]
) -> list[SendResult]:
    all_results: list[SendResult] = []
    for client in clients:
        log.info("platform_send_start", extra={"platform": client.name, "count": len(conversions)})
        results = client.send(conversions)
        ok = sum(1 for r in results if r.status == "ok")
        err = len(results) - ok
        log.info(
            "platform_send_done",
            extra={"platform": client.name, "ok": ok, "error": err},
        )
        all_results.extend(results)
    return all_results


def group_failures(
    conversions: Sequence[Conversion], results: Sequence[SendResult]
) -> dict[str, list[dict]]:
    by_order: dict[str, Conversion] = {c.order_id: c for c in conversions}
    out: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r.status == "error":
            c = by_order.get(r.order_id)
            if c is None:
                continue
            out[r.platform].append(
                {
                    "platform": r.platform,
                    "order_id": c.order_id,
                    "event_id": r.event_id,
                    "event_time": c.event_time.isoformat(),
                    "event_name": c.event_name,
                    "email_hash": c.email_hash,
                    "phone_hash": c.phone_hash,
                    "value": c.value,
                    "currency": c.currency,
                    "error": r.error,
                }
            )
    return out


def failures_to_jsonl(grouped: dict[str, list[dict]]) -> bytes:
    lines: list[str] = []
    for platform in sorted(grouped):
        for item in grouped[platform]:
            lines.append(json.dumps(item, separators=(",", ":")))
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def compute_error_rate(results: Sequence[SendResult]) -> float:
    if not results:
        return 0.0
    errors = sum(1 for r in results if r.status == "error")
    return errors / len(results)


def any_platform_fully_down(results: Sequence[SendResult]) -> str | None:
    by_platform: dict[str, list[SendResult]] = defaultdict(list)
    for r in results:
        by_platform[r.platform].append(r)
    for platform, items in by_platform.items():
        if items and all(r.status == "error" for r in items):
            return platform
    return None


def run(cfg: Config, target: date) -> int:
    log.info(
        "run_start",
        extra={
            "target_date": target.isoformat(),
            "dry_run": cfg.dry_run,
            "enable_tiktok": cfg.enable_tiktok,
            "enable_meta": cfg.enable_meta,
            "enable_snap": cfg.enable_snap,
        },
    )

    conversions = bigquery_source.fetch(
        cfg.gcp_project, cfg.bq_dataset, cfg.bq_table, target
    )

    if not conversions:
        log.warning("no_conversions", extra={"target_date": target.isoformat()})
        return 0

    clients = build_clients(cfg)
    if not clients:
        log.error("no_platforms_enabled")
        return 2

    results = send_to_all(clients, conversions)

    success_bytes = bigquery_source.rows_to_jsonl_bytes(conversions)
    failures = group_failures(conversions, results)
    failure_bytes = failures_to_jsonl(failures)

    date_str = target.isoformat()

    if not cfg.dry_run:
        github_commit.commit_file(
            cfg.github_repo,
            f"data/{date_str}.jsonl",
            success_bytes,
            f"data: conversions for {date_str}",
            cfg.github_pat,
            branch=cfg.github_branch,
        )
        if failures:
            github_commit.commit_file(
                cfg.github_repo,
                f"failures/{date_str}.jsonl",
                failure_bytes,
                f"failures: conversions for {date_str}",
                cfg.github_pat,
                branch=cfg.github_branch,
            )
    else:
        log.info(
            "dry_run_skip_github",
            extra={"success_bytes": len(success_bytes), "failure_bytes": len(failure_bytes)},
        )

    err_rate = compute_error_rate(results)
    down_platform = any_platform_fully_down(results)

    log.info(
        "run_done",
        extra={
            "target_date": date_str,
            "rows": len(conversions),
            "sent_total": len(results),
            "error_rate": err_rate,
            "down_platform": down_platform,
        },
    )

    if down_platform:
        log.error("platform_fully_down", extra={"platform": down_platform})
        return 3
    if err_rate > cfg.error_rate_threshold:
        log.error(
            "error_rate_exceeded",
            extra={"error_rate": err_rate, "threshold": cfg.error_rate_threshold},
        )
        return 4
    return 0


def main() -> int:
    configure_logging()
    cfg = Config.load()
    target = bigquery_source.resolve_target_date(cfg.target_date_override)
    try:
        return run(cfg, target)
    except Exception:
        log.exception("run_failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

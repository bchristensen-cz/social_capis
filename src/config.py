from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise ConfigError(f"missing required env var: {name}")
    return v


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True, slots=True)
class Config:
    gcp_project: str
    bq_dataset: str
    bq_table: str
    github_repo: str
    github_branch: str
    github_pat: str
    tiktok_access_token: str
    tiktok_pixel_code: str
    meta_access_token: str
    meta_dataset_id: str
    snap_access_token: str
    snap_pixel_id: str
    dry_run: bool
    test_event_code: str
    enable_tiktok: bool
    enable_meta: bool
    enable_snap: bool
    error_rate_threshold: float
    target_date_override: str

    @classmethod
    def load(cls) -> Config:
        return cls(
            gcp_project=_required("GCP_PROJECT"),
            bq_dataset=_required("BQ_DATASET"),
            bq_table=_required("BQ_TABLE"),
            github_repo=_optional("GITHUB_REPO", "bchristensen-cz/social_capis"),
            github_branch=_optional("GITHUB_BRANCH", "main"),
            github_pat=_required("GITHUB_PAT"),
            tiktok_access_token=_required("TIKTOK_ACCESS_TOKEN"),
            tiktok_pixel_code=_required("TIKTOK_PIXEL_CODE"),
            meta_access_token=_required("META_ACCESS_TOKEN"),
            meta_dataset_id=_required("META_DATASET_ID"),
            snap_access_token=_required("SNAP_ACCESS_TOKEN"),
            snap_pixel_id=_required("SNAP_PIXEL_ID"),
            dry_run=_bool("DRY_RUN", False),
            test_event_code=_optional("TEST_EVENT_CODE", ""),
            enable_tiktok=_bool("ENABLE_TIKTOK", True),
            enable_meta=_bool("ENABLE_META", True),
            enable_snap=_bool("ENABLE_SNAP", True),
            error_rate_threshold=_float("ERROR_RATE_THRESHOLD", 0.05),
            target_date_override=_optional("TARGET_DATE", ""),
        )

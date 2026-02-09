"""Structured scrape logs: logs/scrape_YYYY-MM-DD.jsonl and scrape_retries_YYYY-MM-DD.jsonl."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def _ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_log(entry: dict[str, Any], log_dir: Path | None = None) -> None:
    dir_ = log_dir or _ensure_log_dir()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = dir_ / f"scrape_{date_str}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()


def log_run_start(
    retailer_count: int,
    max_brands: int | None = None,
    log_dir: Path | None = None,
) -> None:
    """Append run_start event to daily scrape log."""
    entry = {
        "timestamp": _ts(),
        "event": "run_start",
        "retailer_count": retailer_count,
        "max_brands": max_brands,
    }
    _append_log(entry, log_dir)


def log_run_end(
    total_brands: int,
    retailers_processed: int,
    success: bool = True,
    log_dir: Path | None = None,
) -> None:
    entry = {
        "timestamp": _ts(),
        "event": "run_end",
        "total_brands": total_brands,
        "retailers_processed": retailers_processed,
        "success": success,
    }
    _append_log(entry, log_dir)


def log_site_result(
    source: str,
    success: bool,
    brands_count: int = 0,
    error: str | None = None,
    blocked_or_captcha: bool = False,
    log_dir: Path | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": _ts(),
        "event": "site_result",
        "source": source,
        "success": success,
        "brands_count": brands_count,
        "blocked_or_captcha": blocked_or_captcha,
        "error": error,
    }
    _append_log(entry, log_dir)


def log_retry(source: str, attempt: int, reason: str, log_dir: Path | None = None) -> None:
    dir_ = log_dir or _ensure_log_dir()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = dir_ / f"scrape_retries_{date_str}.jsonl"
    entry = {
        "timestamp": _ts(),
        "source": source,
        "attempt": attempt,
        "reason": reason,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()

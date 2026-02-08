"""Reliability report: aggregate scrape JSONL logs by source (success rate, brands, blocked)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scrape_logger import LOG_DIR


def get_reliability_report(
    logs_dir: Path | None = None,
    file_paths: list[Path] | None = None,
    days: int | None = None,
) -> dict[str, Any]:
    """
    Read scrape_*.jsonl logs and aggregate by source.
    Returns dict with log_files, by_source (list of per-source stats).
    If file_paths is given, use those files; else use logs_dir (default LOG_DIR) and optionally days.
    """
    dir_ = logs_dir or LOG_DIR
    if file_paths is not None:
        paths = [Path(p) for p in file_paths if Path(p).exists()]
    else:
        paths = sorted(dir_.glob("scrape_*.jsonl"))
        if days is not None and days > 0:
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
            paths = [p for p in paths if p.name >= f"scrape_{cutoff}.jsonl"]
    paths = sorted(paths)

    by_source: dict[str, list[dict]] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("event") != "site_result":
                        continue
                    src = entry.get("source") or "unknown"
                    by_source.setdefault(src, []).append(entry)
        except OSError:
            continue

    rows = []
    for source in sorted(by_source.keys()):
        entries = by_source[source]
        n = len(entries)
        ok = sum(1 for e in entries if e.get("success"))
        brands = sum(e.get("brands_count") or 0 for e in entries)
        blocked = sum(1 for e in entries if e.get("blocked_or_captcha"))
        last_err = None
        for e in reversed(entries):
            if e.get("error"):
                last_err = (e["error"] or "")[:200]
                break
        rate = (ok / n * 100) if n else 0.0
        rows.append({
            "source": source,
            "runs": n,
            "successes": ok,
            "success_rate_pct": round(rate, 1),
            "total_brands": brands,
            "blocked_count": blocked,
            "last_error": last_err,
        })

    return {
        "log_files": [str(p) for p in paths],
        "by_source": rows,
    }

#!/usr/bin/env python3
"""Print scraping reliability report from JSONL logs (CLI). For API use GET /reliability."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reliability import get_reliability_report
from src.scrape_logger import LOG_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraping reliability report from JSONL logs")
    parser.add_argument(
        "files",
        nargs="*",
        default=None,
        help="Paths to scrape_YYYY-MM-DD.jsonl (default: logs/scrape_*.jsonl)",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=LOG_DIR,
        help="Logs directory when no files given",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Limit to last N days of log files (when no files given)",
    )
    args = parser.parse_args()

    file_paths = [Path(p) for p in args.files] if args.files else None
    report = get_reliability_report(
        logs_dir=args.logs_dir,
        file_paths=file_paths,
        days=args.days,
    )

    paths = report["log_files"]
    rows = report["by_source"]
    if not paths and not rows:
        print("No log files or no site_result entries found.")
        return
    if not rows:
        print("No site_result entries in the given logs.")
        return

    w_source = max(4, max(len(r["source"]) for r in rows))
    w_n = max(3, len(str(max(r["runs"] for r in rows))))
    fmt = ("{{:{}}}  {{:>{}}}  {{:>6.1f}}% ok  {{:>6}} brands  {{:>3}} blocked  {{}}").format(
        w_source, w_n
    )
    print(f"\nScraping reliability (from {len(paths)} log file(s))\n")
    header = f"{'Source':<{w_source}}  {'Runs':>{w_n}}  {'Success':>8}  {'Brands':>6}  {'Blk':>3}  Last error (sample)"
    print(header)
    print("-" * max(len(header), 70))
    for r in rows:
        print(fmt.format(
            r["source"],
            r["runs"],
            r["success_rate_pct"],
            r["total_brands"],
            r["blocked_count"],
            r["last_error"] or "—",
        ))
    print()


if __name__ == "__main__":
    main()

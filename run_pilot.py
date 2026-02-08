#!/usr/bin/env python3
"""
Scrape N retailers, write JSON, optionally send to n8n.
Usage:
  python run_pilot.py                    # default limit=10
  python run_pilot.py 20                 # scrape 20 retailers
  python run_pilot.py --limit 5
  python run_pilot.py --max-brands 100   # stop after 100 brands, show progress
  LIMIT=15 python run_pilot.py
  MAX_BRANDS=100 python run_pilot.py
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.sources import get_pilot_retailers
from src.scraper import run_pilot_sync
from src.webhook import send_to_n8n
from src.schemas import payload_for_n8n
from src.scrape_logger import log_run_start, log_run_end

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOAD_DOTENV = PROJECT_ROOT / ".env"

DEFAULT_LIMIT = 10


def main(
    limit: int | None = None,
    max_brands: int | None = None,
) -> None:
    load_dotenv(LOAD_DOTENV)
    n = limit if limit is not None else int(os.environ.get("LIMIT", DEFAULT_LIMIT))
    n = max(1, min(n, 500))
    if max_brands is None and os.environ.get("MAX_BRANDS"):
        try:
            max_brands = int(os.environ.get("MAX_BRANDS", ""))
        except ValueError:
            max_brands = None
    retailers = get_pilot_retailers(limit=n)
    out_file = OUTPUT_DIR / "pilot_brands.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log_run_start(retailer_count=len(retailers), max_brands=max_brands)
    log_path = PROJECT_ROOT / "logs" / f"scrape_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    print(f"Logs: {log_path}", flush=True)

    def progress_callback(source: str, n_records: int, error: str | None, records_so_far: list, index: int, total: int) -> None:
        total_count = len(records_so_far)
        status = f"{n_records} brands" if error is None else f"failed: {error}"
        print(f"  [{index}/{total}] {source}: {status} (total so far: {total_count})", flush=True)
        # Write partial results so you can see output while it runs
        payload = payload_for_n8n(records_so_far)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Scraping up to {n} retailers" + (f", stop at {max_brands} brands" if max_brands else "") + "...", flush=True)
    records = run_pilot_sync(
        retailers,
        max_retries=2,
        max_brands=max_brands,
        progress_callback=progress_callback,
    )
    print(f"Extracted {len(records)} brand records.", flush=True)

    log_run_end(total_brands=len(records), retailers_processed=len(retailers), success=True)

    payload = payload_for_n8n(records)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_file}")

    ok, msg = send_to_n8n(records)
    if ok:
        print(f"n8n webhook: {msg}")
    else:
        print(f"n8n webhook (optional): {msg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape retailers and send to n8n")
    parser.add_argument("limit", nargs="?", type=int, default=None, help="Max retailers to scrape (default 10)")
    parser.add_argument("--limit", "-n", type=int, default=None, dest="limit_flag", help="Max retailers to scrape")
    parser.add_argument("--max-brands", "-b", type=int, default=None, dest="max_brands", help="Stop once this many brands collected (e.g. 100)")
    args = parser.parse_args()
    main(limit=args.limit_flag or args.limit, max_brands=args.max_brands)

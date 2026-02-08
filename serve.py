#!/usr/bin/env python3
"""
HTTP server so n8n can trigger the scraper by passing a retailers array.

Endpoint:
  POST /scrape   Body: { "retailers": [ { "name": "...", "brand_list_url": "..." }, ... ] }

No CSV in the project; no limit param. You pass the exact list of retailers to scrape.
Returns full result in response body (no webhook push).

Run: python serve.py
Default port: 5000 (set PORT env to override)
"""
from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from src.scraper import run_pilot_sync
from src.schemas import payload_for_n8n

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__)


def _parse_retailers() -> list[SimpleNamespace]:
    """
    Read retailers from POST body: { "retailers": [ { "name": "...", "brand_list_url": "..." }, ... ] }.
    Returns list of objects with .name and .brand_list_url; skips items without brand_list_url.
    """
    if not request.is_json or not isinstance(request.json, dict):
        return []
    raw = request.json.get("retailers")
    if not isinstance(raw, list):
        return []
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        url = (item.get("brand_list_url") or "").strip()
        if not url or url.lower() in ("n/a", "https://n/a"):
            continue
        name = (item.get("name") or "").strip() or f"Retailer_{i + 1}"
        out.append(SimpleNamespace(name=name, brand_list_url=url))
    return out


@app.route("/scrape", methods=["POST"])
def scrape():
    """
    Run scraper on posted retailers. Can take several minutes.
    In n8n HTTP Request node: set Timeout to 300 (seconds) or higher so the request does not time out.
    Optional body: "max_brands": 100 to stop after 100 brands and return sooner.
    """
    retailers = _parse_retailers()
    if not retailers:
        return jsonify({
            "ok": False,
            "error": "No retailers provided. Send JSON body: { \"retailers\": [ { \"name\": \"...\", \"brand_list_url\": \"https://...\" } ] }",
            "retailers_run": 0,
            "records": [],
            "meta": {"count": 0},
        }), 200

    # Cap brands so response returns before n8n timeout (default 100 when single retailer)
    max_brands = None
    if request.is_json and isinstance(request.json, dict):
        if "max_brands" in request.json:
            try:
                max_brands = int(request.json["max_brands"])
                if max_brands < 1:
                    max_brands = None
            except (TypeError, ValueError):
                pass
        # Single retailer + no max_brands → default 100 so n8n gets a quick response
        if max_brands is None and len(retailers) == 1:
            max_brands = 100

    # Shared list so we can return partial result on timeout
    shared_records: list = []
    def _progress(_src: str, _n: int, _err: str | None, records_so_far: list, _idx: int, _total: int) -> None:
        shared_records.clear()
        shared_records.extend(records_so_far)

    server_timeout = 115  # return before n8n 120s so connection doesn't abort
    timed_out = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(
            run_pilot_sync,
            retailers,
            max_retries=2,
            max_brands=max_brands,
            progress_callback=_progress,
        )
        try:
            records = future.result(timeout=server_timeout)
        except concurrent.futures.TimeoutError:
            timed_out = True
            records = list(shared_records)
    # Never return more than max_brands (keeps response small and under n8n timeout)
    if max_brands is not None and len(records) > max_brands:
        records = records[:max_brands]
    payload = payload_for_n8n(records)
    payload["meta"]["partial_timeout"] = timed_out

    return jsonify({
        "ok": True,
        "retailers_run": len(retailers),
        "brands_extracted": len(records),
        "partial_timeout": timed_out,
        "records": payload["records"],
        "meta": payload["meta"],
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

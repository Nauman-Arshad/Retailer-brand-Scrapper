#!/usr/bin/env python3
"""
HTTP server for the scraper.

  POST /scrape         — Single retailer. Body: { "name": "...", "brand_list_url": "..." } or { "retailers": [ one item ] }. Optional: max_brands (default 500).
  POST /scrape-multiple — Multiple retailers. Body: { "retailers": [ ... ], "max_brands_per_retailer": 50 }. Returns results_by_retailer with per-retailer errors.
  GET  /health        — Health check.

Run: python serve.py   (port 5000, or set PORT in .env)
"""
from __future__ import annotations

import concurrent.futures
import os
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from src.scraper import run_pilot_sync
from src.schemas import payload_for_n8n

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__)

SERVER_TIMEOUT = 115  # return before n8n 120s


def _parse_retailers_from_body() -> list[SimpleNamespace]:
    """Read retailers from body.retailers array. Returns list of { name, brand_list_url }."""
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


def _parse_single_retailer() -> SimpleNamespace | None:
    """
    Parse one retailer from body for POST /scrape.
    Accepts: { "name": "...", "brand_list_url": "..." }  or  { "retailers": [ { "name", "brand_list_url" } ] }.
    Returns one SimpleNamespace or None.
    """
    if not request.is_json or not isinstance(request.json, dict):
        return None
    body = request.json
    # Single object with brand_list_url
    if "brand_list_url" in body:
        url = (body.get("brand_list_url") or "").strip()
        if not url or url.lower() in ("n/a", "https://n/a"):
            return None
        name = (body.get("name") or "").strip() or "Retailer"
        return SimpleNamespace(name=name, brand_list_url=url)
    # Array with one item
    retailers = _parse_retailers_from_body()
    if len(retailers) == 1:
        return retailers[0]
    return None


def _run_scraper(
    retailers: list[SimpleNamespace],
    max_brands: int | None = None,
    max_brands_per_retailer: int | None = None,
) -> tuple[list, bool, dict[str, str]]:
    """
    Run scraper with timeout. Returns (records, timed_out, errors_by_source).
    """
    shared_records: list = []
    shared_errors: dict[str, str] = {}

    def _progress(_src: str, _n: int, _err: str | None, records_so_far: list, _idx: int, _total: int) -> None:
        shared_records.clear()
        shared_records.extend(records_so_far)
        if _n == 0 and _err:
            shared_errors[_src] = _err
        elif _n > 0 and _src in shared_errors:
            del shared_errors[_src]

    timed_out = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(
            run_pilot_sync,
            retailers,
            max_retries=2,
            max_brands=max_brands,
            max_brands_per_retailer=max_brands_per_retailer,
            progress_callback=_progress,
        )
        try:
            records = future.result(timeout=SERVER_TIMEOUT)
        except concurrent.futures.TimeoutError:
            timed_out = True
            records = list(shared_records)
    return records, timed_out, shared_errors


# ---------- Single retailer: POST /scrape ----------


@app.route("/scrape", methods=["POST"])
def scrape_single():
    """
    Scrape one retailer only.
    Body: { "name": "Beymen", "brand_list_url": "https://..." }  or  { "retailers": [ { "name", "brand_list_url" } ] }.
    Optional: "max_brands" (default 500 when omitted).
    """
    try:
        retailer = _parse_single_retailer()
        if retailer is None:
            return jsonify({
                "ok": False,
                "error": "Single retailer required. Send { \"name\": \"...\", \"brand_list_url\": \"https://...\" } or { \"retailers\": [ one item ] }. For multiple retailers use POST /scrape-multiple.",
                "records": [],
                "meta": {"count": 0},
            }), 200

        body = request.json if request.is_json and isinstance(request.json, dict) else {}
        max_brands = 500  # default for single
        if "max_brands" in body:
            try:
                v = int(body["max_brands"])
                if v >= 1:
                    max_brands = v
            except (TypeError, ValueError):
                pass

        retailers = [retailer]
        records, timed_out, shared_errors = _run_scraper(retailers, max_brands=max_brands, max_brands_per_retailer=None)
        if max_brands is not None and len(records) > max_brands:
            records = records[:max_brands]

        payload = payload_for_n8n(records)
        payload["meta"]["partial_timeout"] = timed_out

        out = {
            "ok": True,
            "brands_extracted": len(records),
            "partial_timeout": timed_out,
            "records": payload["records"],
            "meta": payload["meta"],
        }
        if len(records) == 0 and retailer.name in shared_errors:
            out["error"] = shared_errors[retailer.name]
        elif len(records) == 0 and timed_out:
            out["error"] = "Server timeout before any brands returned"
        return jsonify(out), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "records": [],
            "meta": {"count": 0},
        }), 500


# ---------- Multiple retailers: POST /scrape-multiple ----------


@app.route("/scrape-multiple", methods=["POST"])
def scrape_multiple():
    """
    Scrape multiple retailers. Body: { "retailers": [ { "name", "brand_list_url" }, ... ] }.
    Optional: "max_brands" (total cap), "max_brands_per_retailer" (e.g. 50 per retailer).
    Returns results_by_retailer (each with brands[] and optional error).
    """
    try:
        retailers = _parse_retailers_from_body()
        if not retailers:
            return jsonify({
                "ok": False,
                "error": "No retailers provided. Send { \"retailers\": [ { \"name\": \"...\", \"brand_list_url\": \"https://...\" }, ... ] }",
                "retailers_run": 0,
                "records": [],
                "results_by_retailer": [],
                "meta": {"count": 0},
            }), 200

        if len(retailers) == 1:
            return jsonify({
                "ok": False,
                "error": "For a single retailer use POST /scrape instead of POST /scrape-multiple.",
                "retailers_run": 0,
                "records": [],
                "results_by_retailer": [],
                "meta": {"count": 0},
            }), 200

        body = request.json if request.is_json and isinstance(request.json, dict) else {}
        max_brands = None
        max_brands_per_retailer = None
        if "max_brands" in body:
            try:
                v = int(body["max_brands"])
                if v >= 1:
                    max_brands = v
            except (TypeError, ValueError):
                pass
        if "max_brands_per_retailer" in body:
            try:
                v = int(body["max_brands_per_retailer"])
                if v >= 1:
                    max_brands_per_retailer = v
            except (TypeError, ValueError):
                pass

        records, timed_out, shared_errors = _run_scraper(
            retailers, max_brands=max_brands, max_brands_per_retailer=max_brands_per_retailer
        )
        if max_brands_per_retailer is None and max_brands is not None and len(records) > max_brands:
            records = records[:max_brands]

        payload = payload_for_n8n(records)
        payload["meta"]["partial_timeout"] = timed_out

        by_source: dict = defaultdict(list)
        for r in records:
            by_source[r.source].append(r.to_dict())

        results_by_retailer = []
        for r in retailers:
            source = r.name
            brands = by_source.get(source, [])
            entry = {"source": source, "brands": brands, "count": len(brands)}
            if len(brands) == 0:
                if source in shared_errors:
                    entry["error"] = shared_errors[source]
                elif timed_out:
                    entry["error"] = "Not run (server timeout)"
            results_by_retailer.append(entry)

        return jsonify({
            "ok": True,
            "retailers_run": len(retailers),
            "brands_extracted": len(records),
            "partial_timeout": timed_out,
            "records": payload["records"],
            "results_by_retailer": results_by_retailer,
            "meta": payload["meta"],
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "records": [],
            "results_by_retailer": [],
            "meta": {"count": 0},
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

#!/usr/bin/env python3
"""Flask API for brand scraping: /scrape, /scrape-multiple, kill switch, status, reliability."""
from __future__ import annotations

import concurrent.futures
import json
import os
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response

from src.normalize import configure_noise
from src.reliability import get_reliability_report
from src.root_page import render as render_root_page, render_logs_page, render_report_page
from src.scraper import LAST_SCRAPE_STATS, run_pilot_sync
from src.schemas import payload_for_n8n
from src.scrape_logger import LOG_DIR, log_run_end, log_run_start, RETAILER_STATUS_FILE

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__)

def _server_timeout_seconds() -> int:
    """Server-side scrape timeout (single or batch). Configurable via SCRAPER_SERVER_TIMEOUT (default 200)."""
    try:
        v = int(os.environ.get("SCRAPER_SERVER_TIMEOUT", "200"))
        return max(60, min(600, v))  # clamp 1–10 min
    except (TypeError, ValueError):
        return 200

ENV_SANDBOX = "sandbox"
ENV_PRODUCTION = "production"


def _kill_switch_enabled() -> bool:
    """Return True if scraper is paused via SCRAPER_KILL_SWITCH or PAUSE_SCRAPER."""
    v = os.environ.get("SCRAPER_KILL_SWITCH", "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    v = os.environ.get("PAUSE_SCRAPER", "").strip().lower()
    return v in ("1", "true", "yes")


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
    """Parse one retailer from body (single object or retailers[0]). Returns None if invalid."""
    if not request.is_json or not isinstance(request.json, dict):
        return None
    body = request.json
    if "brand_list_url" in body:
        url = (body.get("brand_list_url") or "").strip()
        if not url or url.lower() in ("n/a", "https://n/a"):
            return None
        name = (body.get("name") or "").strip() or "Retailer"
        return SimpleNamespace(name=name, brand_list_url=url)
    retailers = _parse_retailers_from_body()
    if len(retailers) == 1:
        return retailers[0]
    return None


def _run_scraper(
    retailers: list[SimpleNamespace],
    max_brands: int | None = None,
    max_brands_per_retailer: int | None = None,
) -> tuple[list, bool, dict[str, str]]:
    """Run scraper with timeout. Returns (records, timed_out, errors_by_source)."""
    shared_records: list = []
    shared_errors: dict[str, str] = {}

    def _progress(_src: str, _n: int, _err: str | None, records_so_far: list, _idx: int, _total: int) -> None:
        shared_records.clear()
        shared_records.extend(records_so_far)
        if _n == 0 and _err:
            shared_errors[_src] = _err
        elif _n > 0 and _src in shared_errors:
            del shared_errors[_src]

    log_run_start(retailer_count=len(retailers), max_brands=max_brands or max_brands_per_retailer)
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
            records = future.result(timeout=_server_timeout_seconds())
        except concurrent.futures.TimeoutError:
            timed_out = True
            records = list(shared_records)
    log_run_end(
        total_brands=len(records),
        retailers_processed=len(retailers),
        success=not timed_out and len(shared_errors) == 0,
    )
    return records, timed_out, shared_errors


@app.route("/scrape/status", methods=["GET"])
def scrape_status():
    """Return kill-switch status: scraper_active, kill_switch_enabled, message."""
    enabled = _kill_switch_enabled()
    return jsonify({
        "scraper_active": not enabled,
        "kill_switch_enabled": enabled,
        "message": "Scraper is paused (kill switch ON). Set SCRAPER_KILL_SWITCH=0 or unset to resume."
        if enabled else "Scraper is active.",
    }), 200


@app.route("/scrape", methods=["POST"])
def scrape_single():
    """POST /scrape: one retailer. Body: name, brand_list_url. Optional: max_brands, environment, noise_words, noise_phrases."""
    try:
        if _kill_switch_enabled():
            return jsonify({
                "ok": False,
                "error": "Scraper is paused (kill switch enabled).",
                "kill_switch": True,
                "records": [],
                "meta": {"count": 0},
            }), 503
        retailer = _parse_single_retailer()
        if retailer is None:
            return jsonify({
                "ok": False,
                "error": "Single retailer required. Send { \"name\": \"...\", \"brand_list_url\": \"https://...\" } or { \"retailers\": [ one item ] }. For multiple retailers use POST /scrape-multiple.",
                "records": [],
                "meta": {"count": 0},
            }), 200

        body = request.json if request.is_json and isinstance(request.json, dict) else {}
        env_raw = (body.get("environment") or "").strip().lower()
        environment = env_raw if env_raw in (ENV_SANDBOX, ENV_PRODUCTION) else ENV_PRODUCTION

        noise_words = body.get("noise_words")
        noise_phrases = body.get("noise_phrases")
        configure_noise(
            extra_words=noise_words if isinstance(noise_words, list) else None,
            extra_phrases=noise_phrases if isinstance(noise_phrases, list) else None,
        )

        max_brands = None
        if "max_brands" in body:
            try:
                v = int(body["max_brands"])
                if v >= 1:
                    max_brands = v
            except (TypeError, ValueError):
                pass

        retailers = [retailer]
        records, timed_out, shared_errors = _run_scraper(
            retailers, max_brands=max_brands, max_brands_per_retailer=None
        )
        if max_brands is not None and len(records) > max_brands:
            records = records[:max_brands]

        payload = payload_for_n8n(records)
        payload["meta"]["partial_timeout"] = timed_out
        stats = LAST_SCRAPE_STATS.get(retailer.name, {})
        if stats:
            payload["meta"]["raw_count"] = int(stats.get("raw_count", 0))
            payload["meta"]["filtered_count"] = int(stats.get("filtered_count", len(records)))

        out = {
            "ok": True,
            "environment": environment,
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


@app.route("/scrape-multiple", methods=["POST"])
def scrape_multiple():
    """POST /scrape-multiple: many retailers. Body: retailers[]. Optional: max_brands, max_brands_per_retailer, environment, noise_words, noise_phrases."""
    try:
        if _kill_switch_enabled():
            return jsonify({
                "ok": False,
                "error": "Scraper is paused (kill switch enabled).",
                "kill_switch": True,
                "retailers_run": 0,
                "records": [],
                "results_by_retailer": [],
                "meta": {"count": 0},
            }), 503
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
        env_raw = (body.get("environment") or "").strip().lower()
        environment = env_raw if env_raw in (ENV_SANDBOX, ENV_PRODUCTION) else ENV_PRODUCTION

        noise_words = body.get("noise_words")
        noise_phrases = body.get("noise_phrases")
        configure_noise(
            extra_words=noise_words if isinstance(noise_words, list) else None,
            extra_phrases=noise_phrases if isinstance(noise_phrases, list) else None,
        )
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
        total_raw = 0
        total_filtered = 0
        seen_sources = set()
        for r in retailers:
            source = r.name
            if source in seen_sources:
                continue
            seen_sources.add(source)
            stats = LAST_SCRAPE_STATS.get(source)
            if stats:
                total_raw += int(stats.get("raw_count", 0))
                total_filtered += int(stats.get("filtered_count", 0))
        if total_raw or total_filtered:
            payload["meta"]["raw_count"] = total_raw
            payload["meta"]["filtered_count"] = total_filtered

        by_source: dict = defaultdict(list)
        for r in records:
            by_source[r.source].append(r.to_dict())

        results_by_retailer = []
        for r in retailers:
            source = r.name
            brands = by_source.get(source, [])
            entry = {"source": source, "brands": brands, "count": len(brands)}
            stats = LAST_SCRAPE_STATS.get(source)
            if stats:
                entry["raw_count"] = int(stats.get("raw_count", 0))
                entry["filtered_count"] = int(stats.get("filtered_count", len(brands)))
            if len(brands) == 0:
                if source in shared_errors:
                    entry["error"] = shared_errors[source]
                elif timed_out:
                    entry["error"] = "Not run (server timeout)"
            results_by_retailer.append(entry)

        return jsonify({
            "ok": True,
            "environment": environment,
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


@app.route("/reliability", methods=["GET"])
def reliability():
    """Return reliability report from logs (by source). Query: ?days=N for last N days."""
    try:
        days = request.args.get("days", type=int)
        report = get_reliability_report(logs_dir=LOG_DIR, days=days)
        return jsonify({"ok": True, **report}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "by_source": [], "log_files": []}), 500


@app.route("/logs", methods=["GET"])
def logs():
    """Return recent log entries for live view. Query: ?days=1&limit=500."""
    try:
        days = request.args.get("days", type=int) or 1
        limit = min(1000, max(1, request.args.get("limit", type=int) or 300))
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        entries: list[dict] = []
        for path in sorted(LOG_DIR.glob("scrape_*.jsonl")):
            if "retries" in path.name:
                if path.name < f"scrape_retries_{cutoff}.jsonl":
                    continue
            else:
                if path.name < f"scrape_{cutoff}.jsonl":
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
                        entry["_file"] = path.name
                        entries.append(entry)
            except OSError:
                continue
        entries.sort(key=lambda e: e.get("timestamp", ""))
        entries = entries[-limit:]
        return jsonify({"ok": True, "entries": entries}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "entries": []}), 500


@app.route("/reports", methods=["GET"])
def reports_page():
    """Full-page reliability report with period filter (today / 7 / 30 days)."""
    return Response(render_report_page(request.url_root), mimetype="text/html; charset=utf-8")


@app.route("/reports/retailer-status", methods=["GET"])
def retailer_status():
    """Lightweight per-retailer execution status for operational monitoring (last run, success/failure, brand count, error)."""
    try:
        if not RETAILER_STATUS_FILE.exists():
            return jsonify({"ok": True, "retailers": {}, "last_updated": None}), 200
        with open(RETAILER_STATUS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        retailers = data.get("retailers") if isinstance(data.get("retailers"), dict) else {}
        return jsonify({
            "ok": True,
            "retailers": retailers,
            "last_updated": data.get("last_updated"),
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "retailers": {}, "last_updated": None}), 500


@app.route("/reports/logs", methods=["GET"])
def logs_page():
    """Full-screen live logs page with auto-refresh."""
    return Response(render_logs_page(request.url_root), mimetype="text/html; charset=utf-8")


@app.route("/", methods=["GET"])
def root():
    return Response(render_root_page(request.url_root), mimetype="text/html; charset=utf-8")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

"""
Send scraped brand payload to n8n webhook.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from .schemas import payload_for_n8n, BrandRecord

# Avoid HTTP 403: browser User-Agent (solution: stackoverflow.com/q/16627227).
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


def get_webhook_url() -> str | None:
    """Read n8n webhook URL from env (e.g. .env via python-dotenv)."""
    return os.environ.get("N8N_WEBHOOK_URL") or None


def send_to_n8n(records: list[BrandRecord], webhook_url: str | None = None) -> tuple[bool, str]:
    """
    POST JSON payload to n8n webhook. Returns (success, message).
    """
    url = webhook_url or get_webhook_url()
    if not url:
        return False, "N8N_WEBHOOK_URL not set"

    payload = payload_for_n8n(records)
    try:
        headers = {"User-Agent": os.environ.get("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT)}
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload, headers=headers)
        if r.is_success:
            return True, f"OK {r.status_code}"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

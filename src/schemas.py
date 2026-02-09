"""Output schema for scraped brand data; compatible with n8n payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json


@dataclass
class BrandRecord:
    brand: str
    source: str
    scrape_timestamp: str

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "source": self.source,
            "scrape_timestamp": self.scrape_timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def make_timestamp() -> str:
    """Return current UTC time in ISO format for scrape_timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload_for_n8n(records: list[BrandRecord]) -> dict:
    """Build response payload with records and meta (count, scrape_timestamp)."""
    return {
        "records": [r.to_dict() for r in records],
        "meta": {
            "count": len(records),
            "scrape_timestamp": make_timestamp(),
        },
    }

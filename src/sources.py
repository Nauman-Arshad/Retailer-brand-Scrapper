"""
Load and validate retailer list from CSV.
Provides pilot subset (10 retailers) and full list with brand-list URLs.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple

# Default path relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
RETAILERS_CSV = CONFIG_DIR / "retailers.csv"


class Retailer(NamedTuple):
    """Single retailer record from the source CSV."""
    name: str
    domain: str
    brand_list_url: str
    primary_geo: str
    retailer_type: str
    segment: str
    priority: str
    status: str
    clean_domain: str


def _is_valid_brand_list_url(url: str) -> bool:
    """Return True if URL is present and not N/A."""
    if not url or not url.strip():
        return False
    u = url.strip().lower()
    return not (u == "n/a" or u == "https://n/a" or u.startswith("https://n/a"))


def load_retailers(csv_path: Path | None = None) -> list[Retailer]:
    """
    Load retailers from CSV. Drops rows without a valid brand_list_url.
    """
    path = csv_path or RETAILERS_CSV
    if not path.exists():
        return []

    retailers: list[Retailer] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("Retailer_brand_list_url") or "").strip()
            if not _is_valid_brand_list_url(url):
                continue
            try:
                r = Retailer(
                    name=(row.get("Retailer Name") or "").strip(),
                    domain=(row.get("Retailer Domain Name") or "").strip(),
                    brand_list_url=url,
                    primary_geo=(row.get("Primary geo") or "").strip(),
                    retailer_type=(row.get("Retailer type") or "").strip(),
                    segment=(row.get("Segment/positioning") or "").strip(),
                    priority=(row.get("Priority") or "").strip(),
                    status=(row.get("Status") or "").strip(),
                    clean_domain=(row.get("clean_domain") or "").strip(),
                )
                if r.name and r.domain:
                    retailers.append(r)
            except (KeyError, TypeError):
                continue
    return retailers


# Domains that often return 403 / block scrapers — try these last so limit=1 still gets data
_TRY_LAST_DOMAINS = frozenset({"24s.com", "aesthet.com"})


def get_pilot_retailers(
    csv_path: Path | None = None,
    limit: int = 10,
    priority: str = "High",
) -> list[Retailer]:
    """
    Return first `limit` High-priority retailers with valid brand list URLs.
    Retailers that often block (e.g. 24S, Aesthet) are tried last so small limits still get data.
    """
    all_r = load_retailers(csv_path)
    eligible = [r for r in all_r if r.priority == priority and r.status == "Active"]
    # Dedupe by clean_domain
    seen: set[str] = set()
    unique: list[Retailer] = []
    for r in eligible:
        if r.clean_domain and r.clean_domain not in seen:
            seen.add(r.clean_domain)
            unique.append(r)
    # Put known-blocked domains last so limit=1 gets a working retailer first
    unique.sort(key=lambda r: (r.clean_domain.lower() in _TRY_LAST_DOMAINS, r.name))
    return unique[:limit]


if __name__ == "__main__":
    all_ = load_retailers()
    pilot = get_pilot_retailers(limit=10)
    print(f"Loaded {len(all_)} retailers with valid brand list URLs")
    print(f"Pilot set: {len(pilot)} retailers")
    for r in pilot:
        print(f"  - {r.name} | {r.brand_list_url}")

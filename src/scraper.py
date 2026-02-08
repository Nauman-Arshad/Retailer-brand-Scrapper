"""
Playwright-based scraper: visit retailer brand-list URLs, extract brand names,
normalize, dedupe, and return structured records. No per-site config — works
generically for any site in the CSV. Uses main-content scoping and href slugs
when link text is missing or noisy.
"""
from __future__ import annotations

import asyncio
import os
import random
import re
from typing import Callable
from urllib.parse import unquote, urlparse

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from .normalize import dedupe_brand_names
from .schemas import BrandRecord, make_timestamp
from .scrape_logger import log_retry, log_site_result


# Delay range (seconds) for anti-bot randomization
async def _delay() -> None:
    min_d = float(os.environ.get("SCRAPE_DELAY_MIN", "1"))
    max_d = float(os.environ.get("SCRAPE_DELAY_MAX", "3"))
    await asyncio.sleep(random.uniform(min_d, max_d))


# Avoid HTTP 403: use a known browser User-Agent (solution: stackoverflow.com/q/16627227).
# Servers block default bot user agents; we use the same pattern as Request + headers.
# Can be overridden with SCRAPER_USER_AGENT env.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


# Generic main-content selectors (try in order; first with links wins). No per-site config.
MAIN_CONTAINER_SELECTORS = [
    "main",
    "[role='main']",
    "#main",
    "#MainContent",
    "#content",
    ".main-content",
    ".page-content",
    ".content",
    "[class*='brand']",
    "[class*='designer']",
]

# Brand-like URL path prefixes (any site) — used to pull slug as brand name when text is bad
BRAND_PATH_PATTERN = re.compile(
    r"/(?:brands?|designers?|collections?|merk|marques?|varumarken|b)/[^/?#]+",
    re.I,
)

# Link selectors that commonly point to brand pages (broad, no static config)
DEFAULT_BRAND_SELECTORS = [
    'a[href*="/brands/"]',
    'a[href*="/designers/"]',
    'a[href*="/brand/"]',
    'a[href*="/designer/"]',
    'a[href*="/collections/"]',
    'a[href*="/merk/"]',
    'a[href*="/marques/"]',
    'a[href*="/varumarken/"]',
    'a[href*="/b/"]',
    '[data-brand] a, .brand-name, .designer-name',
    'a[href*="brand"], a[href*="designer"]',
]


def _slug_from_href(href: str) -> str | None:
    """Extract last path segment from a brand-like URL; decode and clean. Returns None if not usable."""
    if not href or "?" in href.split("#")[0]:
        return None
    path = urlparse(href).path.strip("/")
    if not path:
        return None
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    slug = unquote(segments[-1]).replace("-", " ").strip()
    if len(slug) < 2 or len(slug) > 60 or not re.match(r"^[\w\s\-']+$", slug, re.U):
        return None
    return slug


# Letter-group links (e.g. "C-Ç", "I-I", "O-Ö") — alphabet filter, not brands
_LETTER_GROUP_RE = re.compile(
    r"^[A-Za-z\u00C0-\u024F]{1,3}-[A-Za-z\u00C0-\u024F]{1,3}$", re.UNICODE
)


def _looks_like_button_or_noise(text: str) -> bool:
    """True if link text is likely a button/category, not a brand name."""
    t = (text or "").strip()
    if len(t) < 2 or len(t) > 80:
        return True
    if re.search(r"\b(shop|view|see|all|more|filter|sort|sale|brands?|designers?)\b", t, re.I):
        return True
    if "ana sayfa" in t.lower() or "home page" in t.lower():
        return True
    if _LETTER_GROUP_RE.match(t):
        return True
    if t.isdigit():
        return True
    return False


def _looks_like_brand(text: str) -> bool:
    """Heuristic: avoid product lines, categories, 'Shop X', etc."""
    t = (text or "").strip()
    if len(t) < 2 or len(t) > 80:
        return False
    if re.search(r"\b(shop|view|see|all|more|filter|sort)\b", t, re.I):
        return False
    if t.isdigit():
        return False
    return True


async def _get_main_container(page: Page):
    """
    Return a locator for the main content area (first container that has links), or None.
    No static config — tries generic selectors so it works across many sites.
    """
    for sel in MAIN_CONTAINER_SELECTORS:
        try:
            loc = page.locator(sel)
            if await loc.count() == 0:
                continue
            first = loc.first
            inner = first.locator("a[href]")
            if await inner.count() >= 1:
                return first
        except Exception:
            continue
    return None


async def _extract_from_locator(
    page_or_container, selectors: list[str], max_raw_items: int | None = None
) -> list[str]:
    """
    Extract brand-like strings from links. If max_raw_items is set, stop once we have that many (faster when capping).
    """
    raw: list[str] = []
    seen_slugs: set[str] = set()
    for sel in selectors:
        if max_raw_items is not None and len(raw) >= max_raw_items:
            break
        try:
            els = await page_or_container.locator(sel).all()
            for el in els:
                if max_raw_items is not None and len(raw) >= max_raw_items:
                    break
                text = (await el.text_content() or "").strip()
                href = await el.get_attribute("href") or ""
                if BRAND_PATH_PATTERN.search(href):
                    slug = _slug_from_href(href)
                    if slug and slug.lower() not in seen_slugs:
                        if text and not _looks_like_button_or_noise(text):
                            raw.append(text)
                            seen_slugs.add(text.lower()[:50])
                        else:
                            raw.append(slug)
                            seen_slugs.add(slug.lower())
                elif text and len(text) > 1 and len(text) < 120 and not _looks_like_button_or_noise(text):
                    raw.append(text)
        except Exception:
            continue
    return raw


async def scrape_brands_from_url(
    page: Page,
    url: str,
    source_name: str,
    apply_delay: bool = True,
    max_brands_per_url: int | None = None,
) -> tuple[list[BrandRecord], bool, str | None]:
    """
    Navigate to URL, extract brand-like strings (generic — no per-site config),
    normalize and dedupe. Scopes to main content when possible; uses href slug when link text is noisy.
    If max_brands_per_url is set, return at most that many (faster when n8n only needs a cap).
    Returns (list of BrandRecord, blocked_or_captcha, error_message).
    """
    blocked = False
    if apply_delay:
        await _delay()

    parsed = urlparse(url)
    netloc = (parsed.netloc or "").lower()
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
    # Some sites (e.g. 24S, Aesthet) are stricter — try to look more like a real user
    is_hard_site = any(d in netloc for d in ("24s.com", "aesthet.com"))

    try:
        # On hard sites, first hit the homepage to establish cookies/session
        if is_hard_site and base_url:
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.uniform(2, 4))
            except Exception:
                # If this fails we still try the brand URL
                pass

        # Shorter timeout when capping (faster response for n8n)
        page_timeout = 25000 if max_brands_per_url else 60000
        response = await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout)
        if not response:
            return [], False, "No response"
        if response.status >= 400:
            if response.status in (403, 429, 503):
                blocked = True
            return [], blocked, f"HTTP {response.status}"
        try:
            await page.wait_for_selector("a[href]", timeout=5000 if max_brands_per_url else 10000)
        except PlaywrightTimeout:
            pass

        # When capping, stop DOM extraction early (e.g. 150 candidates for 100 brands after dedupe)
        max_raw = (max_brands_per_url + 50) if max_brands_per_url is not None else None
        container = await _get_main_container(page)
        scope = container if container else page
        raw = await _extract_from_locator(scope, DEFAULT_BRAND_SELECTORS, max_raw_items=max_raw)

        # Fallback: full-page links (also respect max_raw so we don't iterate 3000+ elements)
        if len(raw) < 3 or (max_raw is not None and len(raw) < max_raw):
            for el in await page.locator("a[href]").all():
                if max_raw is not None and len(raw) >= max_raw:
                    break
                text = (await el.text_content() or "").strip()
                href = await el.get_attribute("href") or ""
                if BRAND_PATH_PATTERN.search(href):
                    slug = _slug_from_href(href)
                    if slug and _looks_like_brand(slug):
                        raw.append(slug)
                elif text and _looks_like_brand(text) and not _looks_like_button_or_noise(text):
                    raw.append(text)

        names = dedupe_brand_names(raw)
        if max_brands_per_url is not None and len(names) > max_brands_per_url:
            names = names[:max_brands_per_url]
        ts = make_timestamp()
        records = [BrandRecord(brand=n, source=source_name, scrape_timestamp=ts) for n in names]
        return records, False, None
    except PlaywrightTimeout:
        return [], False, "Timeout"
    except Exception as e:
        err = str(e)
        if "captcha" in err.lower() or "blocked" in err.lower() or "403" in err:
            blocked = True
        return [], blocked, err


def _default_progress_callback(
    source: str,
    n_records: int,
    error: str | None,
    records_so_far: list[BrandRecord],
    index: int,
    total: int,
) -> None:
    """No-op progress callback when none provided."""
    pass


async def run_pilot(
    retailers: list,
    max_retries: int = 2,
    max_brands: int | None = None,
    progress_callback: Callable[[str, int, str | None, list[BrandRecord], int, int], None] | None = None,
) -> list[BrandRecord]:
    """
    Run scraper on a list of retailers (e.g. from get_pilot_retailers()).
    Logs each site result and retries; returns all BrandRecords.
    If max_brands is set, stops once total records >= max_brands.
    progress_callback(source, n_records, error, total_so_far, index, total) is called after each retailer.
    """
    all_records: list[BrandRecord] = []
    on_progress = progress_callback or _default_progress_callback
    total_retailers = len(retailers)
    async with async_playwright() as p:
        # Optional proxy support (set PROXY_SERVER env var, e.g. http://user:pass@host:port)
        launch_kwargs: dict = {"headless": True}
        proxy_server = os.environ.get("PROXY_SERVER")
        if proxy_server:
            launch_kwargs["proxy"] = {"server": proxy_server}

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=os.environ.get("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        for idx, r in enumerate(retailers, start=1):
            if max_brands is not None and len(all_records) >= max_brands:
                break
            source = r.name if hasattr(r, "name") else getattr(r, "get", lambda k, d=None: d)("name") or str(r)
            url = (
                r.brand_list_url
                if hasattr(r, "brand_list_url")
                else getattr(r, "get", lambda k, d=None: d)("brand_list_url")
            )
            if not url:
                log_site_result(source, False, 0, error="No brand list URL")
                on_progress(source, 0, "No brand list URL", all_records, idx, total_retailers)
                continue
            last_error: str | None = None
            last_blocked = False
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    log_retry(source, attempt, last_error or "retry")
                    await _delay()
                try:
                    page = await context.new_page()
                    # Per-page headers: add Referer pointing to site root when possible
                    try:
                        parsed = urlparse(url)
                        base_url = (
                            f"{parsed.scheme}://{parsed.netloc}"
                            if parsed.scheme and parsed.netloc
                            else None
                        )
                    except Exception:
                        base_url = None
                    headers = {"Accept-Language": "en-US,en;q=0.9"}
                    if base_url:
                        headers["Referer"] = base_url
                    await page.set_extra_http_headers(headers)

                    need_now = (max_brands - len(all_records)) if max_brands is not None else None
                    records, blocked, err = await scrape_brands_from_url(
                        page, url, source, apply_delay=(attempt == 0), max_brands_per_url=need_now
                    )
                    await page.close()
                    if err and not records:
                        last_error = err
                        last_blocked = blocked
                        continue
                    # When max_brands is set, only take what we need so we return quickly
                    if max_brands is not None:
                        need = max_brands - len(all_records)
                        if need <= 0:
                            break
                        to_add = records[:need]
                        all_records.extend(to_add)
                        log_site_result(
                            source, True, len(to_add), error=None, blocked_or_captcha=blocked
                        )
                        on_progress(source, len(to_add), None, all_records, idx, total_retailers)
                    else:
                        all_records.extend(records)
                        log_site_result(
                            source, True, len(records), error=None, blocked_or_captcha=blocked
                        )
                        on_progress(source, len(records), None, all_records, idx, total_retailers)
                    break
                except Exception as e:
                    last_error = str(e)
                    last_blocked = "captcha" in last_error.lower() or "403" in last_error
            else:
                log_site_result(
                    source, False, 0, error=last_error, blocked_or_captcha=last_blocked
                )
                on_progress(source, 0, last_error, all_records, idx, total_retailers)

        await context.close()
        await browser.close()
    return all_records


def run_pilot_sync(
    retailers: list,
    max_retries: int = 2,
    max_brands: int | None = None,
    progress_callback: Callable[[str, int, str | None, list[BrandRecord], int, int], None] | None = None,
) -> list[BrandRecord]:
    """Synchronous wrapper for run_pilot."""
    return asyncio.run(
        run_pilot(
            retailers,
            max_retries=max_retries,
            max_brands=max_brands,
            progress_callback=progress_callback,
        )
    )

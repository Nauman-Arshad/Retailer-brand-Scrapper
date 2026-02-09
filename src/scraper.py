"""Playwright-based brand list scraper. Extracts and normalizes brand names from retailer URLs; stateless, no per-site config."""
from __future__ import annotations

import asyncio
import os
import random
import re
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from .normalize import dedupe_brand_names
from .schemas import BrandRecord, make_timestamp
from .scrape_logger import log_retry, log_site_result


async def _delay() -> None:
    min_d = float(os.environ.get("SCRAPE_DELAY_MIN", "1"))
    max_d = float(os.environ.get("SCRAPE_DELAY_MAX", "3"))
    await asyncio.sleep(random.uniform(min_d, max_d))


def _retry_delay_seconds(attempt: int) -> float:
    """Exponential backoff with jitter; attempt is 1-based."""
    base = float(os.environ.get("SCRAPE_RETRY_BASE", "1"))
    cap = float(os.environ.get("SCRAPE_RETRY_CAP", "30"))
    sec = min(cap, base * (2 ** attempt))
    return sec + random.uniform(0, 1)


async def _delay_retry(attempt: int) -> None:
    await asyncio.sleep(_retry_delay_seconds(attempt))


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

LAST_SCRAPE_STATS: dict[str, dict[str, int]] = {}

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

GATHER_CHUNK_SIZE = int(os.environ.get("SCRAPER_GATHER_CHUNK", "200"))

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

NEXT_PAGE_SELECTORS = [
    'a[rel="next"]',
    'a[aria-label="Next"]',
    'a[aria-label="next"]',
    '[class*="pagination"] a[rel="next"]',
    '[class*="pager"] a[rel="next"]',
]
NEXT_PAGE_TEXT_RE = re.compile(r"^(next|›|»|>|suivant|weiter|volgende)$", re.I)


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


_LETTER_GROUP_RE = re.compile(
    r"^[A-Za-z\u00C0-\u024F]{1,3}-[A-Za-z\u00C0-\u024F]{1,3}$", re.UNICODE
)

_TRAILING_DIGITS_RE = re.compile(
    r"^(.+[A-Za-z\u00C0-\u024F])(\d+)$", re.UNICODE
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
    """Return True if text passes basic brand-like checks (length, no nav keywords)."""
    t = (text or "").strip()
    if len(t) < 2 or len(t) > 80:
        return False
    if re.search(r"\b(shop|view|see|all|more|filter|sort)\b", t, re.I):
        return False
    if t.isdigit():
        return False
    return True


def _strip_trailing_ui_counter(text: str) -> str:
    """
    Strip trailing digit-only UI counters that have been concatenated to brand
    names (e.g. 'Only Maternity104' -> 'Only Maternity', 'OVS2' -> 'OVS').

    The rule only applies when:
    - Digits are directly attached at the end of the string
    - The preceding character is a letter (so '1017 Alyx 9SM' is untouched)
    """
    t = (text or "").strip()
    if not t:
        return t
    m = _TRAILING_DIGITS_RE.match(t)
    if not m:
        return t
    prefix, _digits = m.groups()
    return prefix.strip()


async def _get_main_container(page: Page):
    """Return first container from MAIN_CONTAINER_SELECTORS that contains links, or None."""
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
    """Extract brand-like strings from matching links (chunked)."""
    raw: list[str] = []
    seen_slugs: set[str] = set()
    for sel in selectors:
        if max_raw_items is not None and len(raw) >= max_raw_items:
            break
        try:
            els = await page_or_container.locator(sel).all()
            if max_raw_items is not None and len(els) + len(raw) > max_raw_items:
                els = els[: max_raw_items - len(raw)]
            if not els:
                continue
            for start in range(0, len(els), GATHER_CHUNK_SIZE):
                if max_raw_items is not None and len(raw) >= max_raw_items:
                    break
                chunk = els[start : start + GATHER_CHUNK_SIZE]
                texts = await asyncio.gather(*[el.text_content() for el in chunk])
                hrefs = await asyncio.gather(*[el.get_attribute("href") for el in chunk])
                for text, href in zip(texts, hrefs):
                    if max_raw_items is not None and len(raw) >= max_raw_items:
                        break
                    t = (text or "").strip()
                    h = (href or "").strip()
                    if BRAND_PATH_PATTERN.search(h):
                        slug = _slug_from_href(h)
                        if slug and slug.lower() not in seen_slugs:
                            if t and not _looks_like_button_or_noise(t):
                                raw.append(t)
                                seen_slugs.add(t.lower()[:50])
                            else:
                                raw.append(slug)
                                seen_slugs.add(slug.lower())
                    elif t and len(t) > 1 and len(t) < 120 and not _looks_like_button_or_noise(t):
                        raw.append(t)
        except Exception:
            continue
    return raw


async def _get_next_page_url(page: Page, current_url: str) -> str | None:
    """Return absolute URL for next pagination link (rel=next, aria-label, or Next text), or None."""
    try:
        for sel in NEXT_PAGE_SELECTORS:
            loc = page.locator(sel)
            if await loc.count() == 0:
                continue
            href = await loc.first.get_attribute("href")
            if href and href.strip():
                return urljoin(current_url, href.strip())
        all_links = await page.locator("a[href]").all()
        for el in all_links[:100]:
            text = (await el.text_content() or "").strip()
            if NEXT_PAGE_TEXT_RE.match(text):
                href = await el.get_attribute("href")
                if href and href.strip():
                    return urljoin(current_url, href.strip())
    except Exception:
        pass
    return None


async def _extract_one_page_raw(page: Page, max_raw: int | None) -> list[str]:
    """Extract raw brand-like strings from current page (main container + fallback)."""
    container = await _get_main_container(page)
    scope = container if container else page
    raw = await _extract_from_locator(scope, DEFAULT_BRAND_SELECTORS, max_raw_items=max_raw)
    if len(raw) < 3 or (max_raw is not None and len(raw) < max_raw):
        all_els = await page.locator("a[href]").all()
        if max_raw is not None:
            all_els = all_els[: max(0, max_raw - len(raw))]
        if all_els:
            for start in range(0, len(all_els), GATHER_CHUNK_SIZE):
                if max_raw is not None and len(raw) >= max_raw:
                    break
                chunk = all_els[start : start + GATHER_CHUNK_SIZE]
                texts = await asyncio.gather(*[el.text_content() for el in chunk])
                hrefs = await asyncio.gather(*[el.get_attribute("href") for el in chunk])
                for text, href in zip(texts, hrefs):
                    if max_raw is not None and len(raw) >= max_raw:
                        break
                    t = (text or "").strip()
                    h = (href or "").strip()
                    if BRAND_PATH_PATTERN.search(h):
                        slug = _slug_from_href(h)
                        if slug and _looks_like_brand(slug):
                            raw.append(slug)
                    elif t and _looks_like_brand(t) and not _looks_like_button_or_noise(t):
                        raw.append(t)
    return raw


async def scrape_brands_from_url(
    page: Page,
    url: str,
    source_name: str,
    apply_delay: bool = True,
    max_brands_per_url: int | None = None,
) -> tuple[list[BrandRecord], bool, str | None]:
    """Navigate to URL, extract and normalize brand names. Returns (records, blocked, error)."""
    blocked = False
    if apply_delay:
        await _delay()

    parsed = urlparse(url)
    netloc = (parsed.netloc or "").lower()
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
    is_hard_site = any(d in netloc for d in ("24s.com", "aesthet.com"))

    try:
        block_css = os.environ.get("SCRAPER_BLOCK_CSS", "").strip().lower() in ("1", "true", "yes")
        blocked_types = ("image", "font", "media")
        if block_css:
            blocked_types = (*blocked_types, "stylesheet")

        async def _block_heavy(route):
            if route.request.resource_type in blocked_types:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", _block_heavy)

        if is_hard_site and base_url:
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.uniform(2, 4))
            except Exception:
                pass

        default_timeout = 25000 if max_brands_per_url else 60000
        page_timeout = int(os.environ.get("SCRAPER_PAGE_TIMEOUT_MS", "0")) or default_timeout
        wait_until = "commit" if os.environ.get("SCRAPER_FAST_LOAD", "").strip().lower() in ("1", "true", "yes") else "domcontentloaded"
        response = await page.goto(url, wait_until=wait_until, timeout=page_timeout)
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

        max_raw = (max_brands_per_url + 50) if max_brands_per_url is not None else None
        all_raw: list[str] = await _extract_one_page_raw(page, max_raw)

        max_pages = int(os.environ.get("SCRAPER_MAX_PAGES", "10"))
        visited = {url}
        current_url = url

        while True:
            names_so_far = dedupe_brand_names(all_raw)
            if max_brands_per_url is not None and len(names_so_far) >= max_brands_per_url:
                break
            if len(visited) >= max_pages:
                break
            next_url = await _get_next_page_url(page, current_url)
            if not next_url or next_url in visited:
                break
            visited.add(next_url)
            await _delay()
            try:
                resp = await page.goto(next_url, wait_until=wait_until, timeout=page_timeout)
                if not resp or resp.status >= 400:
                    break
            except Exception:
                break
            try:
                await page.wait_for_selector("a[href]", timeout=5000)
            except PlaywrightTimeout:
                pass
            current_url = next_url
            page_raw = await _extract_one_page_raw(page, max_raw)
            all_raw.extend(page_raw)
        if "aboutyou" in netloc:
            all_raw = [_strip_trailing_ui_counter(t) for t in all_raw]

        names = dedupe_brand_names(all_raw)
        if max_brands_per_url is not None and len(names) > max_brands_per_url:
            names = names[:max_brands_per_url]
        ts = make_timestamp()
        records = [BrandRecord(brand=n, source=source_name, scrape_timestamp=ts) for n in names]
        try:
            LAST_SCRAPE_STATS[source_name] = {
                "raw_count": len(all_raw),
                "filtered_count": len(names),
            }
        except Exception:
            pass

        return records, False, None
    except PlaywrightTimeout:
        return [], False, "Timeout"
    except Exception as e:
        err = str(e)
        if "captcha" in err.lower() or "blocked" in err.lower() or "403" in err:
            blocked = True
        return [], blocked, err


def _default_progress_callback(
    _source: str, _n: int, _err: str | None, _records: list, _idx: int, _total: int
) -> None:
    pass


async def _scrape_one_retailer(
    context,
    r,
    idx: int,
    total_retailers: int,
    max_brands_per_retailer: int | None,
    max_brands: int | None,
    max_retries: int,
) -> tuple[int, str, list[BrandRecord], str | None]:
    """Scrape one retailer with retries. Returns (idx, source, records, error)."""
    source = r.name if hasattr(r, "name") else getattr(r, "get", lambda k, d=None: d)("name") or str(r)
    url = (
        r.brand_list_url
        if hasattr(r, "brand_list_url")
        else getattr(r, "get", lambda k, d=None: d)("brand_list_url")
    )
    if not url:
        return (idx, source, [], "No brand list URL")
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            log_retry(source, attempt, last_error or "retry")
            await _delay_retry(attempt)
        page = None
        try:
            page = await context.new_page()
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
            records, _blocked, err = await scrape_brands_from_url(
                page, url, source, apply_delay=(attempt == 0), max_brands_per_url=max_brands_per_retailer
            )
            await page.close()
            page = None
            if err and not records:
                last_error = err
                continue
            return (idx, source, records, None)
        except Exception as e:
            last_error = str(e)
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
    return (idx, source, [], last_error)


async def run_pilot(
    retailers: list,
    max_retries: int = 2,
    max_brands: int | None = None,
    max_brands_per_retailer: int | None = None,
    progress_callback: Callable[[str, int, str | None, list[BrandRecord], int, int], None] | None = None,
) -> list[BrandRecord]:
    """Run scraper on all retailers with optional caps and progress callback."""
    all_records: list[BrandRecord] = []
    on_progress = progress_callback or _default_progress_callback
    total_retailers = len(retailers)
    async with async_playwright() as p:
        launch_kwargs: dict = {"headless": True}
        proxy_server = os.environ.get("PROXY_SERVER")
        if proxy_server:
            launch_kwargs["proxy"] = {"server": proxy_server}
        launch_kwargs["args"] = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=os.environ.get("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        concurrency = int(os.environ.get("SCRAPER_CONCURRENCY", "3"))
        use_parallel = total_retailers > 1 and concurrency > 1

        if use_parallel:
            sem = asyncio.Semaphore(concurrency)

            async def scrape_one(r, idx):
                async with sem:
                    return await _scrape_one_retailer(
                        context, r, idx, total_retailers,
                        max_brands_per_retailer, max_brands, max_retries,
                    )

            results = await asyncio.gather(
                *[scrape_one(r, idx) for idx, r in enumerate(retailers, start=1)],
                return_exceptions=True,
            )
            for k, res in enumerate(results):
                idx = k + 1
                if isinstance(res, Exception):
                    log_site_result("unknown", False, 0, error=str(res))
                    on_progress("unknown", 0, str(res), all_records, idx, total_retailers)
                    continue
                _idx, source, records, err = res
                if err and not records:
                    log_site_result(source, False, 0, error=err)
                    on_progress(source, 0, err, all_records, idx, total_retailers)
                else:
                    if max_brands is not None:
                        need = max_brands - len(all_records)
                        if need > 0:
                            to_add = records[:need]
                            all_records.extend(to_add)
                            log_site_result(source, True, len(to_add), error=None)
                            on_progress(source, len(to_add), None, all_records, idx, total_retailers)
                    else:
                        all_records.extend(records)
                        log_site_result(source, True, len(records), error=None)
                        on_progress(source, len(records), None, all_records, idx, total_retailers)
        else:
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
                        await _delay_retry(attempt)
                    try:
                        page = await context.new_page()
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

                        if max_brands_per_retailer is not None:
                            need_now = max_brands_per_retailer
                        elif max_brands is not None:
                            need_now = max_brands - len(all_records)
                        else:
                            need_now = None
                        records, blocked, err = await scrape_brands_from_url(
                            page, url, source, apply_delay=(attempt == 0), max_brands_per_url=need_now
                        )
                        await page.close()
                        if err and not records:
                            last_error = err
                            last_blocked = blocked
                            continue
                        if max_brands_per_retailer is None and max_brands is not None:
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
    max_brands_per_retailer: int | None = None,
    progress_callback: Callable[[str, int, str | None, list[BrandRecord], int, int], None] | None = None,
) -> list[BrandRecord]:
    """Synchronous entry point for run_pilot (used by Flask)."""
    return asyncio.run(
        run_pilot(
            retailers,
            max_retries=max_retries,
            max_brands=max_brands,
            max_brands_per_retailer=max_brands_per_retailer,
            progress_callback=progress_callback,
        )
    )

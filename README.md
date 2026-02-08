# Retailer Scraping Engine

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## Commands
**Run HTTP server (for n8n)**  
```bash
source .venv/bin/activate && python serve.py
```

**Single retailer — POST /scrape** (default 180 brands)
```bash
curl -s -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{"name": "Beymen", "brand_list_url": "https://www.beymen.com/tr/markalar-1849"}'
```

**Single retailer with limit**
```bash
curl -s -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{"name": "Beymen", "brand_list_url": "https://www.beymen.com/tr/markalar-1849", "max_brands": 100}'
```

**Multiple retailers — POST /scrape-multiple** (e.g. 20 brands per retailer)
```bash
curl -s -X POST http://localhost:5000/scrape-multiple \
  -H "Content-Type: application/json" \
  -d '{
    "retailers": [
      {"name": "24S", "brand_list_url": "https://www.24s.com/en-fr/designers"},
      {"name": "25 South Boutiques", "brand_list_url": "https://www.25southboutiques.com/pages/brands"},
      {"name": "3 Suisses", "brand_list_url": "https://www.3suisses.fr/C-76591-toutes-les-marques.htm"}
    ],
    "max_brands_per_retailer": 20
  }'
```
Use `max_brands_per_retailer` for a limit per retailer. Do not use `max_brands` for multiple if you want N brands each — `max_brands` caps the total across all retailers.

**Pagination (n8n)**  
You send the same POST body as before (e.g. one `brand_list_url`). The server automatically follows “next” links on the site (e.g. page 2, 3…) and returns one combined list of brands. No extra parameters or loops in n8n. Limit how far it goes with `max_brands` or server env `SCRAPER_MAX_PAGES` (default 10 pages per URL).

**Reliability report — GET /reliability**  
Returns scraping stats from logs (by source: runs, success_rate_pct, total_brands, blocked_count). Optional: `?days=7` for last 7 days.
```bash
curl -s http://localhost:5000/reliability
curl -s "http://localhost:5000/reliability?days=7"
```

## Config

- `config/retailers.csv` — optional; columns include `Retailer Name`, `Retailer_brand_list_url`, `Priority`, `Status`. Used by `run_pilot.py`.
- `.env` — `N8N_WEBHOOK_URL`, optional `PORT`, `SCRAPER_USER_AGENT`, `SCRAPE_DELAY_MIN` / `SCRAPE_DELAY_MAX`, `PROXY_SERVER`, `SCRAPER_CONCURRENCY` (3), `SCRAPER_RETRY_BASE` / `SCRAPER_RETRY_CAP`, `SCRAPER_GATHER_CHUNK` (200), `SCRAPER_PAGE_TIMEOUT_MS`, `SCRAPER_BLOCK_CSS`, `SCRAPER_FAST_LOAD`, `SCRAPER_MAX_PAGES` (default 10; max pagination pages per URL).
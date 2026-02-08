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

## Config

- `config/retailers.csv` — optional; columns include `Retailer Name`, `Retailer_brand_list_url`, `Priority`, `Status`. Used by `run_pilot.py`.
- `.env` — `N8N_WEBHOOK_URL`, optional `PORT`, `SCRAPER_USER_AGENT`, `SCRAPE_DELAY_MIN` / `SCRAPE_DELAY_MAX`, `PROXY_SERVER`, `SCRAPER_CONCURRENCY` (default 3), `SCRAPER_RETRY_BASE` / `SCRAPER_RETRY_CAP`, `SCRAPER_GATHER_CHUNK` (200), `SCRAPER_PAGE_TIMEOUT_MS`, `SCRAPER_BLOCK_CSS` (1 to block stylesheets for speed), `SCRAPER_FAST_LOAD` (1 to use `commit` instead of `domcontentloaded` — faster, may miss JS-rendered links).
# Retailer Scraping Engine

Scrape retailer brand-list pages, normalize brand names, and return structured JSON. Use from CLI or via HTTP for n8n.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## Commands

**Run scraper (CSV retailers → JSON + optional n8n webhook)**  
```bash
source .venv/bin/activate && python run_pilot.py
```
- Default: 10 retailers. Override: `python run_pilot.py --limit 5` or `python run_pilot.py --max-brands 100`
- Output: `output/pilot_brands.json`, logs: `logs/scrape_YYYY-MM-DD.jsonl`
- Set `N8N_WEBHOOK_URL` in `.env` to push to n8n

**Run HTTP server (for n8n)**  
```bash
source .venv/bin/activate && python serve.py
```
- Port 5000. POST `/scrape` with body: `{ "retailers": [ { "name": "...", "brand_list_url": "https://..." } ], "max_brands": 100 }`. GET `/health` for health check.
- In n8n set HTTP Request timeout to 120s. Single retailer defaults to 100 brands so the response returns in time.

## Config

- `config/retailers.csv` — optional; columns include `Retailer Name`, `Retailer_brand_list_url`, `Priority`, `Status`. Used by `run_pilot.py`.
- `.env` — `N8N_WEBHOOK_URL`, optional `PORT`, `SCRAPER_USER_AGENT`, `SCRAPE_DELAY_MIN` / `SCRAPE_DELAY_MAX`, `PROXY_SERVER`.

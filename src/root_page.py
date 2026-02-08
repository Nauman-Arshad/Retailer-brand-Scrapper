"""Root landing page HTML for NAIM Brand Scraper. Rendered with base URL from request."""

ROOT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NAIM – Brand Scraper</title>
  <style>
    :root { --bg: #0f0f12; --card: #1a1a20; --text: #e4e4e7; --muted: #71717a; --accent: #a78bfa; --border: #27272a; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: "DM Sans", system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; }
    .wrap { max-width: 640px; margin: 0 auto; padding: 2rem 1.5rem; }
    h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.25rem; }
    .tagline { color: var(--muted); font-size: 0.95rem; margin-bottom: 2rem; }
    section { margin-bottom: 2rem; }
    h2 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 0.75rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.5rem; }
    .card h3 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.25rem; }
    .card p { font-size: 0.85rem; color: var(--muted); }
    .method { display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 0.2em 0.5em; border-radius: 4px; margin-right: 0.5rem; }
    .get { background: #166534; color: #bbf7d0; }
    .post { background: #1e40af; color: #bfdbfe; }
    code { font-family: ui-monospace, monospace; font-size: 0.85em; color: var(--accent); }
    ul { list-style: none; }
    li { padding: 0.35rem 0; font-size: 0.9rem; padding-left: 1.25rem; position: relative; }
    li::before { content: "✓"; position: absolute; left: 0; color: var(--accent); font-weight: 600; }
    .contact { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
    .contact p { font-size: 0.9rem; color: var(--muted); }
    .contact a { color: var(--accent); text-decoration: none; }
    .contact a:hover { text-decoration: underline; }
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="wrap">
    <h1>NAIM – Brand Scraper</h1>
    <p class="tagline">Extract brand lists from retailer pages. JSON API for n8n and automation.</p>

    <section>
      <h2>APIs</h2>
      <div class="card">
        <h3><span class="method get">GET</span> <code>{base}/</code></h3>
        <p>This page. Service info and documentation.</p>
      </div>
      <div class="card">
        <h3><span class="method get">GET</span> <code>{base}/health</code></h3>
        <p>Health check. Returns <code>{"status": "ok"}</code>.</p>
      </div>
      <div class="card">
        <h3><span class="method get">GET</span> <code>{base}/reliability</code></h3>
        <p>Reliability report from logs: by_source (runs, success_rate_pct, total_brands, blocked_count). Query: <code>?days=N</code> for last N days.</p>
      </div>
      <div class="card">
        <h3><span class="method post">POST</span> <code>{base}/scrape</code></h3>
        <p>Single retailer. Body: <code>name</code>, <code>brand_list_url</code>. Optional: <code>max_brands</code> (default 180). Pagination is automatic: server follows “next” links and returns one combined list.</p>
      </div>
      <div class="card">
        <h3><span class="method post">POST</span> <code>{base}/scrape-multiple</code></h3>
        <p>Multiple retailers. Body: <code>retailers[]</code> with <code>name</code>, <code>brand_list_url</code>. Optional: <code>max_brands</code>, <code>max_brands_per_retailer</code>. Pagination is automatic per URL.</p>
      </div>
    </section>

    <section>
      <h2>Features</h2>
      <ul>
        <li>Generic selectors — no per-site config</li>
        <li>Main-content scoping and brand-path slug fallback</li>
        <li>Normalized, deduped brand names</li>
        <li>Parallel retailers and chunked DOM reads</li>
        <li>Resource blocking (images/fonts/media) for faster loads</li>
        <li>Exponential backoff and configurable timeouts</li>
        <li>Structured logs (JSONL) and n8n-ready payloads</li>
        <li>Automatic pagination (follows next page links; no extra n8n steps)</li>
      </ul>
    </section>

    <section class="contact">
      <h2>Contact</h2>
      <p>For support or integration questions, reach out to your team or maintainer.</p>
      <p style="margin-top: 0.5rem;"><a href="mailto:support@example.com">support@example.com</a></p>
    </section>
  </div>
</body>
</html>"""


def render(base_url: str) -> str:
    """Return full HTML for the root page with base_url substituted."""
    return ROOT_HTML.replace("{base}", base_url.rstrip("/"))

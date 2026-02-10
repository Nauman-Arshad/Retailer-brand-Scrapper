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
    .top-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 1.5rem; margin-bottom: 2rem; }
    .top-left { flex: 1 1 auto; }
    .top-actions { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: flex-end; }
    h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.25rem; }
    .tagline { color: var(--muted); font-size: 0.95rem; margin-bottom: 0.25rem; }
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
    .load-err { color: #f87171; }
    .muted { color: var(--muted); }
    .card a { color: var(--accent); text-decoration: none; }
    .card a:hover { text-decoration: underline; }
    .btn-link { display: inline-flex; align-items: center; justify-content: center; padding: 0.4rem 0.9rem; border-radius: 999px; border: 1px solid var(--border); font-size: 0.85rem; font-weight: 500; text-decoration: none; cursor: pointer; white-space: nowrap; }
    .btn-link.primary { background: var(--accent); color: #020617; border-color: transparent; }
    .btn-link.secondary { background: transparent; color: var(--accent); }
    .btn-link:hover { filter: brightness(1.1); }
    @media (max-width: 640px) {
      .top-row { flex-direction: column; align-items: stretch; }
      .top-actions { justify-content: flex-start; }
    }
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="wrap">
    <div class="top-row">
      <div class="top-left">
        <h1>NAIM – Brand Scraper</h1>
        <p class="tagline">Extract brand lists from retailer pages. JSON API for n8n and automation.</p>
      </div>
      <div class="top-actions">
        <a class="btn-link primary" href="/reports">Reliability report</a>
        <a class="btn-link secondary" href="/reports/logs">Live logs</a>
      </div>
    </div>

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
        <h3><span class="method get">GET</span> <code>{base}/reports/retailer-status</code></h3>
        <p>Lightweight per-retailer execution status for operational monitoring: <code>last_run</code>, <code>success</code>, <code>brand_count</code>, <code>error</code> per retailer. Updated after each retailer run.</p>
      </div>
      <div class="card">
        <h3><span class="method get">GET</span> <code>{base}/logs</code></h3>
        <p>Recent log entries for live view. Query: <code>?days=1&limit=500</code>. Used by the <a href="/reports/logs">Live logs</a> page.</p>
      </div>
      <div class="card">
        <h3><span class="method get">GET</span> <code>{base}/scrape/status</code></h3>
        <p>Kill switch status. Returns <code>scraper_active</code>, <code>kill_switch_enabled</code>. Use to check if scraping is paused before calling POST /scrape.</p>
      </div>
      <div class="card">
        <h3><span class="method post">POST</span> <code>{base}/scrape</code></h3>
        <p>Single retailer. Body: <code>name</code>, <code>brand_list_url</code>. Optional: <code>max_brands</code> (omit to scrape all brands), <code>environment</code> (<code>\"sandbox\"</code> or <code>\"production\"</code>), and <code>noise_words</code> / <code>noise_phrases</code> arrays. Pagination is automatic.</p>
      </div>
      <div class="card">
        <h3><span class="method post">POST</span> <code>{base}/scrape-multiple</code></h3>
        <p>Multiple retailers. Body: <code>retailers[]</code> with <code>name</code>, <code>brand_list_url</code>. Optional: <code>max_brands</code>, <code>max_brands_per_retailer</code>, <code>environment</code>, <code>noise_words</code>, <code>noise_phrases</code>. Pagination is automatic per URL.</p>
      </div>
    </section>

    <section>
      <h2>Environment & configuration</h2>
      <div class="card">
        <h3>Sandbox vs production</h3>
        <p>Control scraper mode from the request body:</p>
        <p><code>{\"environment\": \"sandbox\"}</code> → safe test runs (n8n can route to test sheets, lower limits, extra logging).</p>
        <p><code>{\"environment\": \"production\"}</code> (or omit) → live runs (n8n routes to production sheets and monitoring).</p>
        <p><strong>Use sandbox when testing</strong> to avoid accidental large production runs or writing to live sheets.</p>
      </div>
      <div class="card">
        <h3>Workflows: single retailer vs bulk</h3>
        <p><strong>Primary — single retailer (real-time):</strong> Use <code>POST /scrape</code> with your gold sheet trigger. When a new retailer is added to the sheet, the workflow runs the scraper for that retailer and writes all brands to the result sheet.</p>
        <p><strong>Bulk — multiple retailers:</strong> Use <code>POST /scrape-multiple</code> when you need data for many retailers quickly (e.g. first-time backfill or all retailers at once). The server runs them with internal concurrency. If the batch times out (<code>partial_timeout: true</code>) or fails, fall back to <code>POST /scrape</code> once per retailer in a loop.</p>
      </div>
      <div class="card">
        <h3>Noise words & phrases</h3>
        <p>Category labels like <code>Clothing</code> or <code>Handbags</code> are managed in a Google Sheet, not hard-coded.</p>
        <p>n8n reads the <code>Scrapper Noise Words</code> tab and sends <code>noise_words</code> and <code>noise_phrases</code> arrays in the POST body so they can be edited without code changes.</p>
      </div>
      <div class="card">
        <h3>Kill switch</h3>
        <p>Pause all scraping via environment: set <code>SCRAPER_KILL_SWITCH=1</code> or <code>PAUSE_SCRAPER=true</code>. When ON, POST <code>/scrape</code> and <code>/scrape-multiple</code> return 503 and do not run. Check <code>GET {base}/scrape/status</code> for current state. Unset or set to 0/false to resume.</p>
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
        <li>Structured logs (JSONL) and n8n-ready payloads with raw vs filtered counts</li>
        <li>Automatic pagination (follows next page links; no extra n8n steps)</li>
      </ul>
    </section>
  </div>
</body>
</html>"""


REPORT_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reliability report – NAIM Brand Scraper</title>
  <style>
    :root { --bg: #0f0f12; --card: #1a1a20; --text: #e4e4e7; --muted: #71717a; --accent: #a78bfa; --border: #27272a; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: "DM Sans", system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }
    h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem; }
    .toolbar { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
    .toolbar a { color: var(--muted); text-decoration: none; font-size: 0.9rem; }
    .toolbar a:hover { color: var(--accent); }
    .filter { display: flex; gap: 0.5rem; align-items: center; }
    .filter label { color: var(--muted); font-size: 0.9rem; }
    .filter select { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; }
    .reliability-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    .reliability-table th, .reliability-table td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); }
    .reliability-table th { color: var(--muted); font-weight: 500; }
    .reliability-table tr:hover td { background: rgba(255,255,255,0.03); }
    .load-err { color: #f87171; }
    .muted { color: var(--muted); }
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="wrap">
    <div class="toolbar">
      <a href="/">← Home</a>
      <div class="filter">
        <label for="days">Period:</label>
        <select id="days">
          <option value="1">Today</option>
          <option value="7" selected>Last 7 days</option>
          <option value="30">Last 30 days</option>
        </select>
      </div>
    </div>
    <h1>Reliability report</h1>
    <div id="content"><p class="muted">Loading…</p></div>
  </div>
  <script>
(function () {
  function byId(id) { return document.getElementById(id); }
  function escapeHtml(s) { if (s == null) return ''; var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function load() {
    var days = byId('days').value;
    byId('content').innerHTML = '<p class="muted">Loading…</p>';
    fetch('/reliability?days=' + days).then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok || !d.by_source) { byId('content').innerHTML = '<p class="load-err">Failed to load report.</p>'; return; }
        var list = Array.isArray(d.by_source) ? d.by_source : Object.keys(d.by_source).map(function (k) { var r = d.by_source[k]; r.source = r.source || k; return r; });
        if (list.length === 0) {
          byId('content').innerHTML = '<p class="muted">No log data for this period.</p><p class="muted" style="margin-top:0.5rem;">On Fly.io, logs are written to the machine disk. Mount a persistent volume and set <code>SCRAPER_LOG_DIR</code> to that path (see README) so logs survive restarts and the report shows data.</p>';
          return;
        }
        var rows = list.map(function (s) {
          return '<tr><td>' + escapeHtml(s.source) + '</td><td>' + (s.runs ?? '-') + '</td><td>' + (s.success_rate_pct ?? '-') + '%</td><td>' + (s.total_brands ?? '-') + '</td><td>' + (s.blocked_count ?? '-') + '</td><td>' + escapeHtml((s.last_error || '-')) + '</td></tr>';
        }).join('');
        byId('content').innerHTML = '<table class="reliability-table"><thead><tr><th>Source</th><th>Runs</th><th>Success %</th><th>Brands</th><th>Blocked</th><th>Last error</th></tr></thead><tbody>' + rows + '</tbody></table>';
      })
      .catch(function () { byId('content').innerHTML = '<p class="load-err">Could not load report.</p>'; });
  }
  byId('days').addEventListener('change', load);
  load();
})();
  </script>
</body>
</html>"""


LOGS_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live logs – NAIM Brand Scraper</title>
  <style>
    :root { --bg: #0c0c0e; --text: #e4e4e7; --muted: #71717a; --accent: #a78bfa; --border: #27272a; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; overflow: hidden; font-family: ui-monospace, monospace; font-size: 0.85rem; line-height: 1.5; background: var(--bg); color: var(--text); }
    .full { display: flex; flex-direction: column; height: 100vh; }
    .bar { flex: 0 0 auto; padding: 0.5rem 1rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 1rem; }
    .bar a { color: var(--muted); text-decoration: none; }
    .bar a:hover { color: var(--accent); }
    .logs { flex: 1 1 auto; overflow: auto; padding: 1rem; }
    .log-line { margin: 0.15em 0; word-break: break-all; }
    .log-line .ts { color: var(--muted); margin-right: 0.5rem; }
    .log-line .event { color: var(--accent); }
    .log-line .file { color: var(--muted); font-size: 0.8em; }
    .load-err { color: #f87171; }
    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <div class="full">
    <div class="bar">
      <a href="/">← Home</a>
      <span class="muted">Live logs (auto-refresh 3s)</span>
    </div>
    <div id="logs-content" class="logs"><p class="muted">Loading…</p></div>
  </div>
  <script>
(function () {
  function byId(id) { return document.getElementById(id); }
  function escapeHtml(s) { if (s == null) return ''; var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function render(entries) {
    if (!entries || !entries.length) return '<p class="muted">No log entries.</p>';
    var html = entries.map(function (e) {
      var ts = e.timestamp || '';
      var ev = e.event || '';
      var parts = [];
      if (ev === 'run_start') parts.push('run_start', 'retailers=' + (e.retailer_count ?? '-'), 'max_brands=' + (e.max_brands ?? '-'));
      else if (ev === 'run_end') parts.push('run_end', 'total=' + (e.total_brands ?? '-'), 'success=' + (e.success !== false));
      else if (ev === 'site_result') parts.push('site_result', escapeHtml(e.source || ''), (e.success ? 'ok' : 'fail'), (e.brands_count ?? 0) + ' brands', (e.blocked_or_captcha ? 'blocked' : ''), (e.error || ''));
      else parts.push(ev || JSON.stringify(e));
      var line = (typeof parts[0] === 'string' ? parts.join(' ') : parts[0]);
      var file = e._file ? ' <span class="file">' + escapeHtml(e._file) + '</span>' : '';
      return '<div class="log-line"><span class="ts">' + escapeHtml(ts) + '</span><span class="event">' + line + '</span>' + file + '</div>';
    }).join('');
    return html;
  }
  function load() {
    fetch('/logs?days=1&limit=500').then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok || !d.entries) { byId('logs-content').innerHTML = '<p class="load-err">Failed to load logs.</p>'; return; }
        byId('logs-content').innerHTML = render(d.entries);
        var el = byId('logs-content');
        el.scrollTop = el.scrollHeight;
      })
      .catch(function () { byId('logs-content').innerHTML = '<p class="load-err">Could not load logs.</p>'; });
  }
  load();
  setInterval(load, 3000);
})();
  </script>
</body>
</html>"""


def render(base_url: str) -> str:
    """Return full HTML for the root page with base_url substituted."""
    return ROOT_HTML.replace("{base}", base_url.rstrip("/"))


def render_report_page(base_url: str) -> str:
    """Return full HTML for the reliability report page."""
    return REPORT_PAGE_HTML.replace("{base}", base_url.rstrip("/"))


def render_logs_page(base_url: str) -> str:
    """Return full HTML for the full-screen live logs page."""
    return LOGS_PAGE_HTML.replace("{base}", base_url.rstrip("/"))

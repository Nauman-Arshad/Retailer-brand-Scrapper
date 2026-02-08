# Playwright Python image includes Chromium and system deps (match playwright package version)
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY serve.py run_pilot.py ./

# Fly.io uses PORT from env (set in fly.toml)
ENV PORT=8080
EXPOSE 8080

CMD ["python", "serve.py"]

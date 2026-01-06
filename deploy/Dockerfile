FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    NODE_ENV=production \
    PORT=8000 \
    HOST=0.0.0.0 \
    WEB_CONCURRENCY=2

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        curl \
        nodejs \
        npm \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libxrender1 \
        libxss1 \
        libxtst6 \
        libu2f-udev \
        libvulkan1 \
        fonts-liberation \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/api/requirements.txt

COPY tools/scraper/package.json tools/scraper/package-lock.json /app/tools/scraper/
RUN cd /app/tools/scraper && npm ci --omit=dev

COPY . /app

ENV PYTHONPATH=/app/apps/api/src

EXPOSE 8000

CMD ["sh", "-c", "gunicorn -w ${WEB_CONCURRENCY:-2} -k gthread -b 0.0.0.0:${PORT} apps.api.wsgi:app"]

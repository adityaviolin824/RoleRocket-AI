FROM python:3.13-slim

# SINGLE RUN: Node.js + MCP deps (critical)
RUN apt-get update -qq && \
    apt-get install -y \
        curl \
        apt-transport-https \
        ca-certificates \
        gnupg \
        gcc \
        g++ \
        make \
        pkg-config \
        libffi-dev && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p input memory outputs config

ENV PYTHONUNBUFFERED=1
ENV PORT=10000
EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/status')" || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

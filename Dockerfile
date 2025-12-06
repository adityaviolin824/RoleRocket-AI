FROM python:3.13-slim

# Install Node.js + npm (multi-stage for smaller size)
RUN apt-get update && apt-get install -y \
    curl gnupg ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npx && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first (layer caching)
COPY requirements.txt .

# Install Python deps (no cache to avoid bloat)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create dirs
RUN mkdir -p input memory outputs config

# Env vars
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Render expects $PORT
EXPOSE $PORT

# Healthcheck (use /status if available, fallback /docs)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/status || curl -f http://localhost:${PORT}/docs || exit 1

# Correct CMD for Render ($PORT)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]

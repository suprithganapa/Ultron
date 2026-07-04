# ULTRON — production container
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Persistent data lives here (mount a disk / volume at this path in prod)
ENV ULTRON_DATA_DIR=/data
RUN mkdir -p /data

# Cloud hosts inject $PORT; bind all interfaces.
ENV HOST=0.0.0.0 PORT=8000 PUBLIC_MODE=true
EXPOSE 8000

# Use $PORT if provided by the platform, else 8000.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# StadiumMate — container image for Google Cloud Run.
# Cloud Run injects $PORT (default 8080); uvicorn binds to it on 0.0.0.0.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8080

# Shell form so ${PORT} is expanded at runtime by Cloud Run.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

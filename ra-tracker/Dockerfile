FROM python:3.11-slim

# Install PostgreSQL client libraries (required for psycopg2 source build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (overridden by Procfile per service)
CMD ["gunicorn", "ra_tracker.web.app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--graceful-timeout", "30", "--timeout", "60"]

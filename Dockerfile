# MedScript Enterprise Production Container
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-privileged system user for secure runtime execution
RUN groupadd -r medscript && useradd -r -g medscript -d /app -s /sbin/nologin medscript

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure storage directories have write permissions
RUN mkdir -p uploads/prescriptions flask_session && \
    chown -R medscript:medscript /app

USER medscript

EXPOSE 5000

# Health check using the internal /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Production WSGI entry point
CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:5000", "--timeout=60", "wsgi:app"]

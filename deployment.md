# MedScript Production Deployment Guide

This guide outlines deployment procedures for the MedScript platform using Docker, Gunicorn, and reverse proxies (Nginx/Cloudflare).

---

## 1. Environment Configuration

Create a production `.env` file containing:

```env
FLASK_ENV=production
SECRET_KEY=your_secure_generated_64_char_secret_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_or_anon_key
GOOGLE_API_KEY=your_google_ai_vision_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
PORT=5000

# Optional notification channels
EMAIL_USER=alerts@medscript.com
EMAIL_PASSWORD=your_smtp_app_password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

---

## 2. Docker Deployment

Build and run using Docker Compose:

```bash
docker compose build
docker compose up -d
```

Verify the health check:
```bash
curl http://localhost:5000/health
```

---

## 3. Direct Gunicorn Execution

For deployment on Linux VMs (e.g. AWS EC2, DigitalOcean Droplet, GCP Compute Engine):

```bash
pip install -r requirements.txt
gunicorn --workers 4 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - wsgi:app
```

---

## 4. Reverse Proxy Setup (Nginx)

```nginx
server {
    listen 80;
    server_name app.medscript.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/medscript/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    client_max_body_size 16M;
}
```

---

---

## 5. Automated CI/CD Pipelines (GitHub Actions)

MedScript includes enterprise-grade GitHub Actions workflows for continuous integration and delivery.

### Workflow Overview

```text
git push / PR
  ↓
[ci.yml]
  ├── Job 1: Flake8 Code Quality & Linting
  ├── Job 2: Bandit & pip-audit Security Scan
  ├── Job 3: Pytest Matrix (Python 3.11 & 3.12 + poppler-utils)
  └── Job 4: Docker Build & Internal /health Probe
  ↓ (on push to main / release)
[cd.yml]
  ├── Job 1: Build & Publish to GHCR (ghcr.io/hiteshgottapu/med-script:latest)
  ├── Job 2: Automated Remote Deployment (Webhook or SSH)
  └── Job 3: Post-Deploy Smoke Test (HTTP 200 verification on /health)
```

### Required GitHub Repository Secrets

Configure these under **Settings → Secrets and variables → Actions**:

| Secret Name | Purpose | Example / Notes |
|---|---|---|
| `SUPABASE_URL` | Supabase project API URL | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | Supabase service or anon API key | `eyJhbGciOi...` |
| `SECRET_KEY` | Flask session encryption key | 64-character random string |
| `DEPLOY_WEBHOOK_URL` | *(Optional)* Cloud deployment trigger | Render / Railway / CapRover deploy webhook |
| `SSH_HOST` | *(Optional)* Target VM IP / domain | `198.51.100.1` |
| `SSH_USER` | *(Optional)* SSH user | `deploy` or `ubuntu` |
| `SSH_PRIVATE_KEY` | *(Optional)* Private SSH key | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `APP_URL` | *(Optional)* Live domain for smoke testing | `https://app.medscript.com` |

---

## 6. Automated Monitoring & Observability

- **Health Endpoint**: `GET /health` returns JSON `{"status": "healthy", "database": "connected", "version": "2.0.0"}`.
- **Request Tracing**: All incoming requests receive an `X-Request-ID` header tracked across structured server logs.
- **Database Maintenance**: The SQLite commerce database operates in WAL mode (`PRAGMA journal_mode=WAL`). Daily backups can be executed with `sqlite3 medscript_commerce.db ".backup backup.db"`.


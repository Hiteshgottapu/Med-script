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

## 5. Automated Monitoring & Observability

- **Health Endpoint**: `GET /health` returns JSON `{"status": "healthy", "database": "connected"}`.
- **Request Tracing**: All incoming requests receive an `X-Request-ID` header tracked across structured server logs.
- **Database Maintenance**: The SQLite commerce database operates in WAL mode (`PRAGMA journal_mode=WAL`). Daily backups can be executed with `sqlite3 medscript_commerce.db ".backup backup.db"`.

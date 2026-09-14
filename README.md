# MedScript — Clinical AI & Healthcare Workspace

[![MedScript CI](https://github.com/Hiteshgottapu/Med-script/actions/workflows/ci.yml/badge.svg)](https://github.com/Hiteshgottapu/Med-script/actions/workflows/ci.yml)
[![MedScript CD](https://github.com/Hiteshgottapu/Med-script/actions/workflows/cd.yml/badge.svg)](https://github.com/Hiteshgottapu/Med-script/actions/workflows/cd.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Docker Image](https://img.shields.io/badge/docker-GHCR-blue?logo=docker)](https://github.com/Hiteshgottapu/Med-script/pkgs/container/med-script)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-16%20passing-brightgreen.svg)](#test-suite)

MedScript is an enterprise AI-powered clinical workflow and pharmacy commerce platform. It digitizes handwritten prescriptions via Google Vision OCR, performs clinical symptom-disease inference with machine learning, aggregates live multi-source medicine prices from major pharmacies, provides an AI medical copilot powered by Google Gemini, and executes a compliant medicine commerce flow with Schedule H prescription validation.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [CI/CD Pipeline](#cicd-pipeline)
- [Quickstart (Development)](#quickstart-development)
- [Environment Variables](#environment-variables)
- [Production Deployment](#production-deployment)
- [Test Suite](#test-suite)
- [API Reference](#api-reference)
- [License](#license)

---

## Key Features

| Feature | Description |
|---|---|
| **Prescription OCR** | Upload handwritten or printed clinical prescriptions; extract structured patient data, medications, dosages, and doctor notes via Google Cloud Vision AI |
| **AI Clinical Consultant** | Multi-symptom disease prediction (SVM + Random Forest ensemble) with contraindications, dietary advice, and lifestyle recommendations |
| **Live Medicine Search** | Real-time medicine data from PharmEasy, OpenFDA, and RxNorm APIs — normalized, deduplicated, and displayed side-by-side with price comparison |
| **Medicine Commerce** | Persistent cart, Schedule H prescription validation, checkout, payment gateway stub, and order management with external pharmacy links |
| **AI Medical Copilot** | Conversational clinical assistant with persistent session history, powered by Google Gemini 1.5 Flash |
| **Doctor Consultation** | Clinical doctor matching and appointment booking workflows |
| **Emergency Dispatch** | Geolocation-aware emergency hospital discovery and alert dispatch |
| **Security Layer** | Rate limiting, CSRF protection, SQL injection prevention, session fingerprinting, Bandit SAST + pip-audit CVE scanning in CI |

---

## Architecture Overview

MedScript uses a **Flask Application Factory** pattern with modular Blueprints to isolate concerns cleanly across the HTTP, service, and data layers.

```
+----------------------------------------------------------+
|                        CLIENTS                           |
|          Browser (Jinja2 + CSS + Vanilla JS)             |
+----------------------+-----------------------------------+
                       | HTTP / AJAX
+----------------------v-----------------------------------+
|                    FLASK APPLICATION                     |
|  Application Factory: app.py                            |
|                                                         |
|  Blueprints (blueprints/)                               |
|  +-- main         -> Dashboard / home routes            |
|  +-- auth         -> Register / login / session         |
|  +-- chat         -> AI copilot conversation            |
|  +-- consultant   -> Symptom -> disease inference       |
|  +-- doctor       -> Doctor matching & appointments     |
|  +-- medicine     -> Search, cart, checkout, orders     |
|  +-- prescription -> OCR upload & extraction            |
|                                                         |
|  Core Layer (core/)                                     |
|  +-- middleware   -> Rate limiting, security headers    |
|  +-- responses    -> Standardised JSON response helpers |
|  +-- exceptions   -> Centralised error handling         |
|  +-- logging      -> Structured application logging     |
+----------------------+-----------------------------------+
                       |
+----------------------v-----------------------------------+
|                    SERVICE LAYER                         |
|  services/medicine/                                     |
|  +-- search.py        -> Aggregates results from sources|
|  +-- normalizer.py    -> Normalises heterogeneous data  |
|  +-- deduplicator.py  -> Merges duplicate listings      |
|  +-- validators.py    -> Schedule H / Rx checks         |
|  +-- orders.py        -> Order lifecycle management     |
|  +-- payments.py      -> Payment gateway adapter        |
|  +-- cache.py         -> In-memory TTL result cache     |
|  +-- database.py      -> SQLite commerce DB helpers     |
|  +-- sources/                                           |
|      +-- base.py      -> Abstract pharmacy source       |
|      +-- openfda.py   -> OpenFDA public API adapter     |
|      +-- rxnorm.py    -> NIH RxNorm API adapter         |
|      +-- pharmeasy.py -> PharmEasy web adapter          |
|                                                         |
|  services/auth/         -> Auth helpers                 |
|  services/chat/         -> Gemini chat session service  |
|  services/consultant/   -> ML model inference service   |
|  services/prescription/ -> Vision OCR pipeline          |
|  services/notifications/-> Alert / notification service |
+----------------------+-----------------------------------+
                       |
+----------------------v-----------------------------------+
|                    DATA LAYER                            |
|  +-- Supabase (PostgreSQL) -- Users, auth, Rx data      |
|  +-- SQLite (WAL mode)    -- Medicine commerce & cart   |
|  |   medscript_commerce.db                              |
|  +-- model/               -- Trained ML artefacts      |
|      +-- rf.pkl   (Random Forest -- ~7 MB)              |
|      +-- svc.pkl  (SVM classifier -- ~400 KB)           |
+----------------------------------------------------------+
```

### Medicine Commerce Data Flow

```
User Query
    |
    v
MedicineSearchService.search()
    |  parallel fetch
    +---> OpenFDA API  --+
    +---> RxNorm API  ---> Normalizer -> Deduplicator -> Ranked results
    +---> PharmEasy   --+
                           |
                           v
                    Side-by-side comparison UI
                           |
                    User selects product
                           |
                 +---------+---------+
                 |  MedScript Cart   |
                 |  (SQLite)         |
                 +---------+---------+
                           |
              Schedule H validator (Rx check)
                           |
                      Checkout form
                           |
                Payment gateway adapter
                           |
              Order record + External source link
```

---

## Project Structure

```
Med-script/
|
+-- app.py                      # Application factory & blueprint registration
+-- config.py                   # Environment-based configuration classes
+-- extensions.py               # Flask extension singletons (db, login, etc.)
+-- wsgi.py                     # Gunicorn WSGI entry point
+-- train_model.py              # ML model training script
|
+-- blueprints/                 # HTTP route handlers (thin controllers)
|   +-- __init__.py
|   +-- main.py                 # Dashboard & home
|   +-- auth.py                 # Authentication (register, login, logout)
|   +-- chat.py                 # AI copilot routes
|   +-- consultant.py           # Symptom -> disease prediction routes
|   +-- doctor.py               # Doctor discovery & appointments
|   +-- medicine.py             # Search, cart, checkout, orders, payments
|   +-- prescription.py         # OCR upload & extraction
|
+-- core/                       # Cross-cutting framework utilities
|   +-- __init__.py
|   +-- exceptions.py           # Custom exception hierarchy
|   +-- logging.py              # Structured logging configuration
|   +-- middleware.py           # Rate limiting, security headers
|   +-- responses.py            # Standardised API response helpers
|
+-- services/                   # Business logic (no Flask dependencies)
|   +-- auth/                   # Auth helpers
|   +-- chat/                   # Gemini session management
|   +-- consultant/             # ML inference pipeline
|   +-- notifications/          # Alert & notification service
|   +-- prescription/           # Google Vision OCR pipeline
|   +-- medicine/               # Medicine commerce engine
|       +-- __init__.py
|       +-- search.py           # Multi-source search aggregation
|       +-- normalizer.py       # Schema normalisation
|       +-- deduplicator.py     # Cross-source deduplication
|       +-- validators.py       # Schedule H / eligibility checks
|       +-- orders.py           # Order lifecycle management
|       +-- payments.py         # Payment adapter
|       +-- cache.py            # TTL in-memory cache
|       +-- database.py         # SQLite commerce helpers
|       +-- models.py           # Medicine data models / schemas
|       +-- sources/
|           +-- base.py         # Abstract base source class
|           +-- openfda.py      # OpenFDA public API
|           +-- rxnorm.py       # NIH RxNorm API
|           +-- pharmeasy.py    # PharmEasy adapter
|
+-- model/                      # Trained ML model artefacts
|   +-- rf.pkl                  # Random Forest classifier
|   +-- svc.pkl                 # SVM classifier
|
+-- dataset/                    # CSV datasets (symptoms, medications, etc.)
|
+-- templates/                  # Jinja2 HTML templates
+-- static/                     # CSS, JS, and image assets
|   +-- design-system.css       # Global design tokens & component styles
|   +-- medicine_search.css     # Medicine search page styles
|   +-- medicine_search.js      # Search, cart drawer, comparison UI logic
|
+-- tests/                      # Pytest test suites (16 tests, all passing)
|   +-- conftest.py
|   +-- test_health_and_core.py
|   +-- test_consultant.py
|   +-- test_medicine_commerce.py
|   +-- test_prescription_ocr.py
|   +-- test_security.py
|
+-- .github/
|   +-- workflows/
|       +-- ci.yml              # Quality gate: lint, SAST, test, docker build
|       +-- cd.yml              # Continuous delivery: GHCR publish + deploy
|       +-- security.yml        # Scheduled weekly security scan
|
+-- Dockerfile                  # Production container definition
+-- docker-compose.yml          # Development compose stack
+-- docker-compose.prod.yml     # Production compose with resource limits
+-- .dockerignore
+-- .env.example                # Environment variable template
+-- requirements.txt
+-- deployment.md               # Full production deployment guide
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 / 3.12 |
| **Web Framework** | Flask (Application Factory, Blueprints) |
| **Templating** | Jinja2 |
| **Frontend** | Vanilla CSS (design-system.css), Vanilla JS |
| **Auth & Database** | Supabase (PostgreSQL + GoTrue Auth) |
| **Commerce Cache** | SQLite (WAL mode) |
| **AI / LLM** | Google Gemini 3.7 Flash (primary), 3.8 Flash, 2.0 Flash (fallbacks) |
| **OCR** | Google Cloud Vision API |
| **ML Classifiers** | Scikit-Learn (SVM + Random Forest ensemble) |
| **External APIs** | OpenFDA, NIH RxNorm, PharmEasy |
| **WSGI Server** | Gunicorn |
| **Reverse Proxy** | Nginx |
| **Containerisation** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions |
| **Container Registry** | GitHub Container Registry (GHCR) |
| **Security Scanning** | Bandit (SAST), pip-audit (CVE) |

---

## CI/CD Pipeline

Three GitHub Actions workflows form the full quality and delivery gate:

```
git push / pull_request
        |
        v
+---------------------------------------------+
|  ci.yml -- Quality Gate                     |
|                                             |
|  +-- Lint & Syntax      Flake8              |
|  +-- Security Audit     Bandit SAST         |
|  |                      pip-audit CVE scan  |
|  +-- Test Matrix        Pytest (16 tests)   |
|  |                      Python 3.11 & 3.12  |
|  +-- Container Build    Docker Buildx       |
|                         /health probe       |
+----------------+----------------------------+
                 | on push to main / tag
                 v
+---------------------------------------------+
|  cd.yml -- Continuous Delivery              |
|                                             |
|  +-- Build & Tag   ghcr.io image            |
|  |                 (latest + sha + semver)  |
|  +-- Publish       GitHub Container Registry|
|  +-- Deploy        Webhook / SSH + Docker   |
|  |                 Compose pull & up -d     |
|  +-- Smoke Test    curl /health endpoint    |
+---------------------------------------------+
                 | on schedule (weekly)
                 v
+---------------------------------------------+
|  security.yml -- Scheduled Security Scan   |
|                                             |
|  +-- Bandit + pip-audit on main branch      |
+---------------------------------------------+
```

### Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `GHCR_TOKEN` | GitHub Container Registry push token |
| `DEPLOY_HOST` | Production server hostname / IP |
| `DEPLOY_USER` | SSH deploy user |
| `DEPLOY_KEY` | SSH private key for deployment |
| `DEPLOY_WEBHOOK_URL` | Managed platform webhook (alternative to SSH) |

---

## Quickstart (Development)

### 1. Clone the repository

```bash
git clone https://github.com/Hiteshgottapu/Med-script.git
cd Med-script
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 5. Run the application

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

### 6. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FLASK_ENV` | Yes | `development` or `production` |
| `SECRET_KEY` | Yes | Flask session secret key |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/service key |
| `GOOGLE_API_KEY` | Yes | Google Cloud Vision API key |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `DATABASE_URL` | No | Override default SQLite path |
| `REDIS_URL` | No | Redis URL for production session store |

See [`.env.example`](.env.example) for a complete template.

---

## Production Deployment

Full guides are in [deployment.md](deployment.md), covering:

- **Docker Compose** on a Linux VM
- **Nginx** reverse proxy with TLS termination
- **Gunicorn** worker configuration
- **CI/CD secrets** setup in GitHub

Quick production start:

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## Test Suite

16 automated tests across 5 suites, verified against Python 3.11 and 3.12:

| Suite | Coverage Area |
|---|---|
| `test_health_and_core.py` | Health endpoint, config loading, CORS |
| `test_consultant.py` | Symptom prediction, ML model inference |
| `test_medicine_commerce.py` | Search, cart, deduplication, order flow |
| `test_prescription_ocr.py` | OCR upload, extraction, validation |
| `test_security.py` | Rate limiting, CSRF, injection prevention |

Run the suite:

```bash
pytest tests/ -v
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (CI/CD probe) |
| `POST` | `/auth/login` | User login |
| `POST` | `/auth/register` | User registration |
| `GET` | `/medicine/search?q=` | Live multi-source medicine search |
| `POST` | `/medicine/cart/add` | Add item to cart |
| `GET` | `/medicine/cart` | View cart contents |
| `POST` | `/medicine/checkout` | Submit order / checkout |
| `GET` | `/medicine/orders` | Order history |
| `POST` | `/consultant/predict` | Symptom -> disease prediction |
| `POST` | `/prescription/upload` | OCR prescription upload |
| `POST` | `/chat/message` | AI copilot message |
| `GET` | `/doctor/list` | Browse doctors |

---

## License

This project is for educational purposes.

---

**Developed by:**
- Hitesh Gottapu
- Jaswanth Kollipara

See [developers page](https://clinnovators.onrender.com/developers) for more info.

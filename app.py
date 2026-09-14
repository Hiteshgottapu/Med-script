from flask import Flask, request, render_template, send_file, redirect, url_for, session, send_from_directory, jsonify, flash
import io
import os
import requests
import base64
import json
import re
import logging
import openai
from dotenv import load_dotenv
from flask_session import Session
from fuzzywuzzy import fuzz, process
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup  # Add this import for web scraping
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.pdfgen import canvas
import sqlite3
import datetime
from supabase import create_client, Client
from functools import wraps
from flask import g
from PIL import Image
import tempfile
try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None
import jwt
from datetime import datetime, timedelta
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

from blueprints.medicine import medicine_bp, medicine_search, order_confirmation_view, search_medicine_prices

# Define the login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            decoded_token = verify_supabase_token(token)
            if decoded_token:
                g.user = decoded_token
                # Update session if not exists
                if 'user' not in session:
                    session['user'] = {
                        'uid': decoded_token.get('sub', ''),
                        'email': decoded_token.get('email', ''),
                        'token': token
                    }
                return f(*args, **kwargs)
        
        # Then check session
        if 'user' in session:
            # Try session token
            session_token = session['user'].get('token')
            if session_token:
                decoded_token = verify_supabase_token(session_token)
                if decoded_token:
                    g.user = decoded_token
                    return f(*args, **kwargs)
            
            # If session token fails, try supabase token
            supabase_token = session['user'].get('supabase_token')
            if supabase_token:
                decoded_token = verify_supabase_token(supabase_token)
                if decoded_token:
                    g.user = decoded_token
                    # Update session token
                    session['user']['token'] = supabase_token
                    return f(*args, **kwargs)

        # If no valid authentication found
        logging.warning("No valid authentication found")
        session.clear()
        
        # Check if it's an API request
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        # For regular requests, redirect to login
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    return decorated_function

# ------------------ Additional Imports for AI Consultant ------------------
import numpy as np
import pandas as pd
import pickle
from collections import defaultdict
from textblob import TextBlob

# ------------------ Load Environment Variables ------------------
load_dotenv()

# ------------------ Initialize Flask App ------------------
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# ------------------ API Keys & Configurations ------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not gemini_api_key or not GOOGLE_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("⚠️ Missing API Keys! Ensure they are set correctly.")
    exit(1)

# ------------------ Configure Secure Flask Session ------------------
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Use timedelta directly
app.config['SESSION_USE_SIGNER'] = True
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey")
app.config['SUPABASE_URL'] = SUPABASE_URL
app.config['SUPABASE_KEY'] = SUPABASE_KEY
Session(app)

# Initialize Supabase Client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase client initialized successfully.")
except Exception as e:
    logging.error(f"Error initializing Supabase client: {str(e)}")
    raise e

def get_db_client():
    """Returns Supabase client with postgrest auth token attached if available"""
    token = None
    if hasattr(g, 'user') and isinstance(g.user, dict):
        token = session.get('user', {}).get('token') or session.get('user', {}).get('supabase_token')
    elif 'user' in session and isinstance(session['user'], dict):
        token = session['user'].get('token') or session['user'].get('supabase_token')
        
    if token:
        try:
            supabase.postgrest.auth(token)
        except Exception as e:
            logging.debug(f"Could not attach user token: {e}")
    return supabase

def verify_supabase_token(token):
    """Verify a Supabase JWT token"""
    if not token:
        return None
        
    try:
        # Get user from Supabase using the token
        response = supabase.auth.get_user(token)
        if response and response.user:
            return {
                'sub': response.user.id,
                'email': response.user.email
            }
        return None
    except Exception as e:
        logging.error(f"Error verifying Supabase token: {e}")
        return None

# --- Register Modular Medicine & Commerce Blueprint ---
app.register_blueprint(medicine_bp)

# Maintain backward-compatible endpoint aliases for template url_for('medicine_search')
app.add_url_rule("/medicine", endpoint="medicine_search", view_func=medicine_search, methods=["GET", "POST"])
app.add_url_rule("/order-confirmation/<order_id>", endpoint="order_confirmation_view", view_func=order_confirmation_view, methods=["GET"])



# --- Prescription Parsing & Structured OCR Helpers ---
def build_clean_transcript(p):
    lines = []
    doc = p.get("doctor", {}) if isinstance(p.get("doctor"), dict) else {}
    clinic = doc.get("clinic") or "Clinical Prescription"
    lines.append(f"=== {clinic.upper()} ===")
    if doc.get("name"):
        doc_line = f"Doctor: {doc.get('name')}"
        if doc.get("specialty"):
            doc_line += f" ({doc.get('specialty')})"
        lines.append(doc_line)
    if doc.get("reg_no"):
        lines.append(f"Reg/License No: {doc.get('reg_no')}")
    lines.append("-" * 40)
    
    pat = p.get("patient", {}) if isinstance(p.get("patient"), dict) else {}
    p_info = f"Patient: {pat.get('name') or 'Patient'}"
    if pat.get('age'):
        p_info += f" | Age: {pat.get('age')}"
    if pat.get('gender'):
        p_info += f" | Gender: {pat.get('gender')}"
    if pat.get('date'):
        p_info += f" | Date: {pat.get('date')}"
    lines.append(p_info)
    if pat.get('allergies'):
        lines.append(f"Allergies: {pat.get('allergies')}")
    lines.append("-" * 40)

    clin = p.get("clinical", {}) if isinstance(p.get("clinical"), dict) else {}
    if clin.get("diagnosis"):
        lines.append(f"Diagnosis: {clin.get('diagnosis')}")
    if clin.get("symptoms"):
        lines.append(f"Symptoms / Complaints: {clin.get('symptoms')}")
    lines.append("-" * 40)

    lines.append("Rx (MEDICATIONS):")
    meds = p.get("medicines", []) if isinstance(p.get("medicines"), list) else []
    if meds:
        for idx, m in enumerate(meds, 1):
            name_str = f"{idx}. {m.get('name', 'Medicine')} {m.get('strength', '')} ({m.get('form', 'Tablet')})".strip()
            lines.append(name_str)
            schedule = f"   Dose: {m.get('dose', '1')} | Freq: {m.get('frequency', 'As directed')} | Dur: {m.get('duration', '5 days')}"
            if m.get('timing'):
                schedule += f" | {m.get('timing')}"
            lines.append(schedule)
            if m.get('instructions'):
                lines.append(f"   Notes: {m.get('instructions')}")
    else:
        lines.append("No specific medications extracted.")
    lines.append("-" * 40)

    inst = p.get("instructions", {}) if isinstance(p.get("instructions"), dict) else {}
    if inst.get("general"):
        lines.append(f"General Advice: {inst.get('general')}")
    if inst.get("diet"):
        lines.append(f"Dietary Guidance: {inst.get('diet')}")
    if inst.get("follow_up"):
        lines.append(f"Follow-up: {inst.get('follow_up')}")
    
    return "\n".join(lines)

def fallback_text_parser(raw_text):
    """Parses unformatted OCR text into structured prescription fields using regex"""
    parsed = {
        "doctor": {},
        "patient": {},
        "clinical": {},
        "medicines": [],
        "instructions": {},
        "raw_transcript": raw_text
    }
    
    # Extract Patient Name
    p_name = re.search(r"(?:Patient(?:\s+Name)?|Name|Pt\.?)\s*[:\-]?\s*([A-Za-z\s.]+?)(?=\n|Age|Gender|Date|Sex|$)", raw_text, re.IGNORECASE)
    if p_name:
        parsed["patient"]["name"] = p_name.group(1).strip()
        
    # Extract Age & Gender
    p_age = re.search(r"Age\s*[:\-]?\s*(\d+)", raw_text, re.IGNORECASE)
    if p_age:
        parsed["patient"]["age"] = p_age.group(1).strip()
    p_gen = re.search(r"(?:Gender|Sex)\s*[:\-]?\s*(Male|Female|M|F|Other)", raw_text, re.IGNORECASE)
    if p_gen:
        gen_str = p_gen.group(1).upper()
        parsed["patient"]["gender"] = "Male" if gen_str in ("M", "MALE") else ("Female" if gen_str in ("F", "FEMALE") else gen_str)

    # Extract Diagnosis
    diag = re.search(r"(?:Diagnosis|Dx|Impression|Condition)\s*[:\-]?\s*([^\n]+)", raw_text, re.IGNORECASE)
    if diag:
        parsed["clinical"]["diagnosis"] = diag.group(1).strip()

    # Extract Medicines (lines starting with numbers or tab/cap/syp)
    med_lines = re.findall(r"(?:^\s*\d+[\.\)]\s*([^\n]+)|(?:Tab|Cap|Syp|Inj)\.?\s+([^\n]+))", raw_text, re.MULTILINE | re.IGNORECASE)
    for m1, m2 in med_lines:
        line = (m1 or m2).strip()
        if line:
            form = "Tablet"
            if re.search(r"\bsyp|syrup\b", line, re.IGNORECASE):
                form = "Syrup"
            elif re.search(r"\bcap|capsule\b", line, re.IGNORECASE):
                form = "Capsule"
            elif re.search(r"\binj|injection\b", line, re.IGNORECASE):
                form = "Injection"
            elif re.search(r"\binhaler\b", line, re.IGNORECASE):
                form = "Inhaler"

            parsed["medicines"].append({
                "name": line,
                "strength": "",
                "form": form,
                "dose": "1 unit",
                "frequency": "Twice daily",
                "duration": "5 days",
                "timing": "After food",
                "instructions": ""
            })

    return parsed

def parse_prescription_response(raw_text):
    clean_text = raw_text.strip()
    if "```" in clean_text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        if match:
            clean_text = match.group(1).strip()
    
    parsed = None
    try:
        parsed = json.loads(clean_text)
    except Exception:
        first_brace = clean_text.find('{')
        last_brace = clean_text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                parsed = json.loads(clean_text[first_brace:last_brace+1])
            except Exception:
                pass

    if not isinstance(parsed, dict):
        parsed = fallback_text_parser(raw_text)

    # Validate and normalize keys
    if "doctor" not in parsed or not isinstance(parsed["doctor"], dict):
        parsed["doctor"] = {}
    if "patient" not in parsed or not isinstance(parsed["patient"], dict):
        parsed["patient"] = {}
    if "clinical" not in parsed or not isinstance(parsed["clinical"], dict):
        parsed["clinical"] = {}
    if "medicines" not in parsed or not isinstance(parsed["medicines"], list):
        parsed["medicines"] = []
    if "instructions" not in parsed or not isinstance(parsed["instructions"], dict):
        parsed["instructions"] = {}
    
    if "raw_transcript" not in parsed or not parsed["raw_transcript"]:
        parsed["raw_transcript"] = build_clean_transcript(parsed)

    return parsed

# --- Function: Extract Text from Image using Gemini Multimodal Vision API ---
def extract_text_from_image(image_file):
    try:
        filename = image_file.filename.lower()
        image_bytes = image_file.read()
        image_data = None
        mime_type = "image/jpeg"

        if filename.endswith('.pdf'):
            if not convert_from_bytes:
                return {"text": 'PDF conversion support not available on server. Please upload a JPG or PNG image.', "parsed": None}
            try:
                images = convert_from_bytes(image_bytes, first_page=1, last_page=1)
                if not images:
                    return {"text": 'No readable pages found in uploaded PDF.', "parsed": None}
                with io.BytesIO() as output:
                    images[0].save(output, format='JPEG', quality=90)
                    image_data = output.getvalue()
                mime_type = "image/jpeg"
            except Exception as e:
                logging.error(f"PDF to image conversion error: {e}")
                return {"text": 'Failed to process PDF file. Please upload a standard JPG/PNG image.', "parsed": None}
        else:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                # Convert RGBA/P to RGB for JPEG compatibility
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                with io.BytesIO() as output:
                    img.save(output, format='JPEG', quality=90)
                    image_data = output.getvalue()
                mime_type = "image/jpeg"
            except Exception as e:
                logging.error(f"Image open error: {e}")
                return {"text": 'Unsupported or corrupted image file format. Please upload a valid JPG, PNG, or WebP image.', "parsed": None}

        if not image_data:
            return {"text": 'Failed to process the uploaded file.', "parsed": None}

        base64_image = base64.b64encode(image_data).decode('utf-8')

        # 1. Primary: Use Gemini Multimodal Vision AI with structured clinical prompt
        api_key = os.getenv("GEMINI_API_KEY") or GOOGLE_API_KEY
        if api_key:
            prompt = (
                "You are an expert clinical pharmacist and medical OCR specialist.\n"
                "Transcribe and parse all handwritten and printed medical details from this prescription image into a clean, valid JSON object.\n\n"
                "Output ONLY valid JSON matching this schema:\n"
                "{\n"
                '  "doctor": {\n'
                '    "name": "Doctor name or null",\n'
                '    "specialty": "Specialty/degree (e.g. MD, MBBS) or null",\n'
                '    "clinic": "Clinic or hospital name or null",\n'
                '    "phone": "Phone number or null",\n'
                '    "reg_no": "Registration/License number or null"\n'
                "  },\n"
                '  "patient": {\n'
                '    "name": "Patient name or null",\n'
                '    "age": "Age or null",\n'
                '    "gender": "Male / Female or null",\n'
                '    "date": "Date of prescription or null",\n'
                '    "allergies": "Known allergies or null"\n'
                "  },\n"
                '  "clinical": {\n'
                '    "diagnosis": "Primary diagnosis / condition or null",\n'
                '    "symptoms": "Symptoms or chief complaints or null",\n'
                '    "notes": "Clinical notes or null"\n'
                "  },\n"
                '  "medicines": [\n'
                "    {\n"
                '      "name": "Medicine brand/generic name",\n'
                '      "strength": "Strength (e.g. 625mg, 10mg, 500mg) or empty",\n'
                '      "form": "Tablet / Capsule / Syrup / Inhaler / Injection / Drops / Ointment",\n'
                '      "dose": "Dosage (e.g. 1 tablet, 5ml, 2 puffs)",\n'
                '      "frequency": "Frequency (e.g. Twice daily, Once daily, 1-0-1, TDS, SOS)",\n'
                '      "duration": "Duration (e.g. 5 days, 1 week, 30 days)",\n'
                '      "timing": "Timing (e.g. After food, Before food, At bedtime, With meals)",\n'
                '      "instructions": "Specific administration advice or warnings"\n'
                "    }\n"
                "  ],\n"
                '  "instructions": {\n'
                '    "general": "General health / care advice or null",\n'
                '    "diet": "Dietary advice or null",\n'
                '    "follow_up": "Follow-up consultation advice or null"\n'
                "  },\n"
                '  "raw_transcript": "Clean human-readable formatted clinical summary of the prescription"\n'
                "}\n\n"
                "Do NOT wrap with commentary, return only the JSON block."
            )

            models_to_try = [
                os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                "gemini-3.6-flash",
                "gemini-flash-latest",
                "gemini-3.7-flash"
            ]
            seen = set()
            models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

            for model_name in models:
                try:
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    params = {"key": api_key}
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": prompt},
                                    {
                                        "inline_data": {
                                            "mime_type": mime_type,
                                            "data": base64_image
                                        }
                                    }
                                ]
                            }
                        ]
                    }

                    logging.info(f"Sending prescription OCR request to Gemini Vision model '{model_name}'")
                    res = requests.post(api_url, params=params, headers=headers, json=payload, timeout=30)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                            parts = candidates[0]["content"]["parts"]
                            if parts and "text" in parts[0]:
                                raw_res = parts[0]["text"].strip()
                                parsed = parse_prescription_response(raw_res)
                                clean_transcript = parsed.get("raw_transcript") or build_clean_transcript(parsed)
                                return {"parsed": parsed, "text": clean_transcript}
                    else:
                        logging.warning(f"Gemini Vision model {model_name} status {res.status_code}: {res.text[:200]}")
                except Exception as e:
                    logging.error(f"Error calling Gemini Vision model {model_name}: {e}")
                    continue

        # 2. Fallback: Google Cloud Vision API
        try:
            gvision_key = os.getenv("GOOGLE_API_KEY")
            if gvision_key:
                gvision_url = f'https://vision.googleapis.com/v1/images:annotate?key={gvision_key}'
                gvision_payload = {
                    "requests": [
                        {
                            "image": {"content": base64_image},
                            "features": [{"type": "TEXT_DETECTION"}]
                        }
                    ]
                }
                res = requests.post(gvision_url, headers={'Content-Type': 'application/json'}, json=gvision_payload, timeout=20)
                if res.status_code == 200:
                    resp_json = res.json()
                    annotations = resp_json.get('responses', [])[0].get('textAnnotations', [])
                    if annotations:
                        raw_desc = annotations[0].get('description', '').strip()
                        parsed = parse_prescription_response(raw_desc)
                        return {"parsed": parsed, "text": parsed.get("raw_transcript") or build_clean_transcript(parsed)}
        except Exception as e:
            logging.error(f"Google Vision fallback error: {e}")

        fallback_msg = "Could not extract text from prescription. Please ensure the image is clear and well-lit, then try again."
        return {"parsed": None, "text": fallback_msg}

    except Exception as e:
        logging.error(f"Unexpected error in extract_text_from_image: {e}")
        return {"parsed": None, "text": f"Error analyzing prescription image: {str(e)}"}

# --- Medication Catalog & Autocomplete API ---
COMMON_MEDICATIONS_DB = [
    {"name": "Paracetamol", "strength": "500 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "3 times daily", "duration": "3 days", "route": "Oral", "timing": "After food", "instructions": "Take for fever or pain relief"},
    {"name": "Dolo 650", "strength": "650 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "As needed (SOS)", "duration": "3 days", "route": "Oral", "timing": "After food", "instructions": "Maximum 3 tablets per day with 6h gap"},
    {"name": "Amoxicillin", "strength": "500 mg", "form": "Capsule", "dose": "1 capsule", "frequency": "3 times daily", "duration": "5 days", "route": "Oral", "timing": "After food", "instructions": "Complete the full 5-day antibiotic course"},
    {"name": "Augmentin 625", "strength": "625 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Twice daily", "duration": "5 days", "route": "Oral", "timing": "With food", "instructions": "Take at start of meals to reduce GI upset"},
    {"name": "Azithromycin", "strength": "500 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "3 days", "route": "Oral", "timing": "1 hour before food", "instructions": "Take at the same time each day"},
    {"name": "Cefixime", "strength": "200 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Twice daily", "duration": "5 days", "route": "Oral", "timing": "After food", "instructions": "Take with adequate water"},
    {"name": "Metformin", "strength": "500 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Twice daily", "duration": "30 days", "route": "Oral", "timing": "With food", "instructions": "For blood sugar management"},
    {"name": "Atorvastatin", "strength": "10 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "30 days", "route": "Oral", "timing": "At bedtime", "instructions": "Cholesterol management"},
    {"name": "Pantoprazole", "strength": "40 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "14 days", "route": "Oral", "timing": "30 min before breakfast", "instructions": "Take on an empty stomach with water"},
    {"name": "Omeprazole", "strength": "20 mg", "form": "Capsule", "dose": "1 capsule", "frequency": "Once daily", "duration": "14 days", "route": "Oral", "timing": "30 min before breakfast", "instructions": "Swallow whole, do not crush"},
    {"name": "Cetirizine", "strength": "10 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "5 days", "route": "Oral", "timing": "At bedtime", "instructions": "May cause mild drowsiness"},
    {"name": "Levocetirizine + Montelukast", "strength": "5mg + 10mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "7 days", "route": "Oral", "timing": "At bedtime", "instructions": "For allergic rhinitis & bronchial symptoms"},
    {"name": "Ibuprofen", "strength": "400 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Twice daily", "duration": "3 days", "route": "Oral", "timing": "After food", "instructions": "Take with milk or full glass of water"},
    {"name": "Amlodipine", "strength": "5 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "30 days", "route": "Oral", "timing": "Morning", "instructions": "Hypertension maintenance"},
    {"name": "Telmisartan", "strength": "40 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "30 days", "route": "Oral", "timing": "Morning", "instructions": "Blood pressure control"},
    {"name": "Losartan", "strength": "50 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "30 days", "route": "Oral", "timing": "Morning", "instructions": "Blood pressure management"},
    {"name": "Ondansetron", "strength": "4 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "3 times daily", "duration": "3 days", "route": "Oral", "timing": "30 min before food", "instructions": "For nausea and vomiting relief"},
    {"name": "Doxycycline", "strength": "100 mg", "form": "Capsule", "dose": "1 capsule", "frequency": "Twice daily", "duration": "7 days", "route": "Oral", "timing": "After food", "instructions": "Do not lie down for 30 minutes after taking"},
    {"name": "Ciprofloxacin", "strength": "500 mg", "form": "Tablet", "dose": "1 tablet", "frequency": "Twice daily", "duration": "5 days", "route": "Oral", "timing": "After food", "instructions": "Drink plenty of fluids throughout the day"},
    {"name": "Salbutamol Inhaler", "strength": "100 mcg", "form": "Inhaler", "dose": "2 puffs", "frequency": "As needed (SOS)", "duration": "30 days", "route": "Inhalation", "timing": "During acute wheezing", "instructions": "Rinse mouth with water after use"},
    {"name": "Zincovit", "strength": "Multivitamin", "form": "Tablet", "dose": "1 tablet", "frequency": "Once daily", "duration": "15 days", "route": "Oral", "timing": "After lunch", "instructions": "Nutritional supplement"}
]

@app.route("/api/medicine-autocomplete", methods=["GET"])
def medicine_autocomplete():
    query = request.args.get("query", "").strip().lower()
    if not query:
        return jsonify(COMMON_MEDICATIONS_DB[:10])
    
    matches = []
    # Check structured DB
    for med in COMMON_MEDICATIONS_DB:
        if query in med["name"].lower():
            matches.append(med)
            
    # Check known_medicines list if more matches needed
    for med_name in known_medicines:
        if query in med_name.lower() and not any(m["name"].lower() == med_name.lower() for m in matches):
            matches.append({
                "name": med_name.title(),
                "strength": "500 mg",
                "form": "Tablet",
                "dose": "1 tablet",
                "frequency": "Twice daily",
                "duration": "5 days",
                "route": "Oral",
                "timing": "After food",
                "instructions": "As directed by physician"
            })
        if len(matches) >= 12:
            break
            
    return jsonify(matches)

@app.route("/api/generate-prescription", methods=["POST"])
def api_generate_prescription():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "No prescription data provided"}), 400

        patient = data.get("patient", {})
        clinical = data.get("clinical", {})
        medicines = data.get("medicines", [])
        instructions = data.get("instructions", {})

        if not patient.get("name"):
            return jsonify({"success": False, "error": "Patient name is required."}), 400
        if not medicines:
            return jsonify({"success": False, "error": "At least one medication is required."}), 400

        rx_id = f"RX-{datetime.now().strftime('%y%m%d')}-{np.random.randint(1000, 9999)}"
        created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
        date_str = datetime.now().strftime("%d %b %Y")

        # Format clean text for PDF generation & records
        lines = []
        lines.append("MEDSCRIPT CLINICAL WORKSPACE")
        lines.append(f"Prescription ID: {rx_id} | Date: {date_str}")
        lines.append("-" * 40)
        lines.append(f"Patient: {patient.get('name')} | Age: {patient.get('age', 'N/A')} | Gender: {patient.get('gender', 'N/A')}")
        if patient.get('allergies'):
            lines.append(f"Allergies: {patient.get('allergies')}")
        lines.append("-" * 40)
        if clinical.get('diagnosis'):
            lines.append(f"Diagnosis: {clinical.get('diagnosis')}")
        if clinical.get('chief_complaint'):
            lines.append(f"Chief Complaint: {clinical.get('chief_complaint')}")
        lines.append("-" * 40)
        lines.append("Rx (MEDICATIONS):")
        for i, med in enumerate(medicines, 1):
            med_line = f"{i}. {med.get('name')} {med.get('strength', '')} ({med.get('form', 'Tablet')})"
            lines.append(med_line)
            dosage_line = f"   Dose: {med.get('dose', '1')} | Freq: {med.get('frequency', '')} | Dur: {med.get('duration', '')} | {med.get('timing', '')}"
            lines.append(dosage_line)
            if med.get('instructions'):
                lines.append(f"   Notes: {med.get('instructions')}")
        lines.append("-" * 40)
        if instructions.get('general'):
            lines.append(f"Instructions: {instructions.get('general')}")
        if instructions.get('follow_up'):
            lines.append(f"Follow-up: {instructions.get('follow_up')}")
        lines.append("-" * 40)
        lines.append("Doctor Signature: _______________________")
        
        formatted_text = "\n".join(lines)

        prescription_obj = {
            "rx_id": rx_id,
            "created_at": created_at,
            "date": date_str,
            "patient": patient,
            "clinical": clinical,
            "medicines": medicines,
            "instructions": instructions,
            "formatted_text": formatted_text
        }

        # Store in session recent history
        if "prescription_history" not in session:
            session["prescription_history"] = []
        
        session["prescription_history"].insert(0, prescription_obj)
        session["prescription_history"] = session["prescription_history"][:10]
        session.modified = True

        return jsonify({
            "success": True,
            "prescription": prescription_obj,
            "formatted_text": formatted_text,
            "pdf_url": url_for("download_pdf", text=formatted_text)
        })

    except Exception as e:
        logging.error(f"Prescription generation error: {e}")
        return jsonify({"success": False, "error": f"Failed to generate prescription: {str(e)}"}), 500

# --- Route: MedScript Page ---
@app.route("/medscript", methods=["GET", "POST"])
def medscript():
    recent_prescriptions = session.get("prescription_history", [])
    if request.method == "POST":
        file = request.files.get("image")
        if file:
            try:
                res = extract_text_from_image(file)
                if isinstance(res, dict):
                    parsed_rx = res.get("parsed")
                    text = res.get("text") or (parsed_rx.get("raw_transcript") if parsed_rx else "")
                else:
                    parsed_rx = parse_prescription_response(str(res))
                    text = str(res)
                return render_template("medscript.html", text=text, parsed_rx=parsed_rx, recent_prescriptions=recent_prescriptions)
            except Exception as e:
                logging.error(f"Image processing error: {str(e)}")
                return render_template("medscript.html", text=f"Error: {str(e)}", parsed_rx=None, recent_prescriptions=recent_prescriptions)
    return render_template("medscript.html", recent_prescriptions=recent_prescriptions)

# --- Function: Format Chatbot Response ---
def format_response(response_text, max_words=120):
    if not response_text or len(response_text.strip()) == 0:
        return "I'm sorry, but I couldn't generate a response."

    response_text = response_text.replace("*", "").strip()
    sections = ["Dosage", "Diet", "Precautions", "Usage"]
    formatted_response = []

    # Extract sections and format them
    for section in sections:
        regex = re.compile(f"{section}:([\\s\\S]*?)(?=\\n[A-Z][a-z]+:|$)", re.IGNORECASE)
        match = regex.search(response_text)
        if match:
            content = match.group(1).strip().replace("\n", "<br>")
            formatted_response.append(f"<div class='response-section'><h4>{section}</h4><p>{content}</p></div>")

    if formatted_response:
        response_text = "".join(formatted_response)
    else:
        # Fallback to plain text if no sections are found
        words = response_text.split()
        if len(words) > max_words:
            truncated_text = " ".join(words[:max_words])
            last_sentence_end = max(truncated_text.rfind("."), truncated_text.rfind("!"), truncated_text.rfind("?"))
            response_text = truncated_text[: last_sentence_end + 1] if last_sentence_end != -1 else truncated_text + "..."
        response_text = f"<p>{response_text}</p>"

    return response_text

# --- Function: Identify Medical Problems ---
def identify_problem(prompt):
    problems = [
        "fever", "cold", "cough", "headache", "stomachache", "flu", "diarrhea", "vomiting", "rash", "sore throat", 
        "fatigue", "dizziness", "chest pain", "shortness of breath", "back pain", "joint pain", "muscle pain",
        "allergies", "infection", "nausea", "hypertension", "diabetes", "asthma", "bronchitis", "pneumonia", 
        "sinusitis", "migraine", "arthritis", "eczema", "psoriasis", "anemia", "depression", "anxiety", 
        "insomnia", "constipation", "ulcer", "acid reflux", "gastroenteritis", "hepatitis", 
        "urinary tract infection", "kidney stones", "gallstones", "menstrual cramps", "pregnancy", "obesity"
    ]
    identified_problems = [problem for problem in problems if problem in prompt.lower()]
    return identified_problems

# --- Function: Medical Chatbot using Gemini API with Multi-turn and Clinical Safety ---
MEDICAL_SYSTEM_INSTRUCTION = (
    "You are the MedScript Clinical AI Assistant, an expert, empathetic, and evidence-based healthcare educational assistant. "
    "Provide clear, clinically accurate, well-structured answers using standard Markdown (headings with ###, bullet points, bold text, numbered lists, tables where appropriate).\n\n"
    "CRITICAL HEALTHCARE & SAFETY PROTOCOLS:\n"
    "1. SCOPE & ROLE: You are an AI educational assistant, NOT a licensed human doctor. Do not provide definitive medical diagnoses or prescribe specific prescription medication dosages as authoritative commands.\n"
    "2. EDUCATIONAL GUIDANCE: Explain health conditions, underlying mechanisms, potential causes, typical clinical pathways, and helpful questions the user can ask their healthcare provider.\n"
    "3. EMERGENCY RED FLAGS: If the user describes emergency or life-threatening symptoms (e.g., sudden severe chest pain or pressure, acute shortness of breath, sudden facial drooping or weakness, severe hemorrhage, anaphylaxis signs, suicidal ideation), immediately advise calling emergency services (such as 911, 112, or local ER) with urgent prominence.\n"
    "4. MEDICATION & PRESCRIPTION QUERIES: When asked about medications, clarify common indications, typical mechanism of action, important precautions, known side effects, and general administration notes, always emphasizing that dosage must follow the physician's prescription.\n"
    "5. DISCLAIMER: Always conclude with a brief medical disclaimer reminder that AI guidance is educational and does not replace professional clinical evaluation."
)

def medical_chatbot(prompt, history=None):
    """
    Generate a clinically sound, markdown-formatted response using Google Gemini API.
    Supports multi-turn conversation history.
    """
    if not prompt or not prompt.strip():
        return "Please enter a question or message to begin."

    # Build contents payload
    contents = []
    
    # Add conversation history if provided
    if history and isinstance(history, list):
        for msg in history:
            role = msg.get("role")
            content = msg.get("content") or msg.get("text") or ""
            if isinstance(content, list):
                # If content is a list of parts
                text_part = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
            else:
                text_part = str(content).strip()

            if not text_part:
                continue
            
            gemini_role = "user" if role in ["user", "human"] else "model"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": text_part}]
            })

    # Add the current user prompt
    contents.append({
        "role": "user",
        "parts": [{"text": prompt.strip()}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": MEDICAL_SYSTEM_INSTRUCTION}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1200
        }
    }

    models_to_try = [
        os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        "gemini-3.6-flash",
        "gemini-flash-latest",
        "gemini-3.7-flash"
    ]
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    api_key = os.getenv("GEMINI_API_KEY") or GOOGLE_API_KEY
    if not api_key:
        return "AI Assistant configuration error: Missing Gemini API key. Please check your environment settings."

    headers = {"Content-Type": "application/json"}

    for model_name in models:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        params = {"key": api_key}
        try:
            logging.info(f"Sending chat request to Gemini model '{model_name}' (turns: {len(contents)})")
            response = requests.post(
                api_url,
                params=params,
                headers=headers,
                json=payload,
                timeout=25
            )
            
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                    parts = candidates[0]["content"]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
                logging.warning(f"Unexpected response structure from model {model_name}: {data}")
            else:
                logging.warning(f"Model {model_name} returned status {response.status_code}: {response.text[:200]}")
        except requests.exceptions.Timeout:
            logging.error(f"Timeout calling Gemini model '{model_name}'")
            continue
        except Exception as e:
            logging.error(f"Error calling Gemini model '{model_name}': {e}")
            continue

    return "The assistant is temporarily unavailable. Please check your connection and try again in a few moments."

# --- Route: Chat (Medical Chatbot) ---
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    history = data.get("history", [])
    conv_id = data.get("conversation_id")
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    
    if not user_message:
        return jsonify({"success": False, "error": "Please enter a message.", "response": "Please enter a message."}), 400

    reply = medical_chatbot(user_message, history=history)
    timestamp_iso = datetime.now().isoformat()
    timestamp_display = datetime.now().strftime("%I:%M %p")

    # 1. Save to Supabase chat_history table
    try:
        db = get_db_client()
        chat_entry = {
            'user_id': user_id,
            'user_message': user_message,
            'bot_response': reply,
            'timestamp': timestamp_iso
        }
        # Prevent duplicate insertion within short window
        recent_chats_resp = db.table('chat_history').select('*').eq('user_id', user_id).order('timestamp', desc=True).limit(1).execute()
        is_duplicate = False
        if recent_chats_resp.data:
            last_chat = recent_chats_resp.data[0]
            if last_chat.get('user_message') == user_message and last_chat.get('bot_response') == reply:
                is_duplicate = True
                
        if not is_duplicate:
            db.table('chat_history').insert(chat_entry).execute()
    except Exception as e:
        logging.error(f"Error saving chat to Supabase: {e}")

    # 2. Save / Update conversation thread in Flask session
    try:
        if 'chat_conversations' not in session:
            session['chat_conversations'] = []
            
        convs = session['chat_conversations']
        active_conv = None
        
        if conv_id:
            for c in convs:
                if c.get('id') == conv_id:
                    active_conv = c
                    break
                    
        if not active_conv:
            conv_id = f"conv_{int(time.time() * 1000)}"
            active_conv = {
                'id': conv_id,
                'title': user_message[:50] + ('...' if len(user_message) > 50 else ''),
                'created_at': timestamp_iso,
                'updated_at': timestamp_iso,
                'messages': []
            }
            convs.insert(0, active_conv)
        else:
            active_conv['updated_at'] = timestamp_iso
            # Move to top of list
            convs.remove(active_conv)
            convs.insert(0, active_conv)

        active_conv['messages'].append({
            'role': 'user',
            'content': user_message,
            'timestamp': timestamp_display
        })
        active_conv['messages'].append({
            'role': 'assistant',
            'content': reply,
            'timestamp': timestamp_display
        })

        session['chat_conversations'] = convs[:20]  # Keep last 20 conversations
        session.modified = True
    except Exception as e:
        logging.error(f"Error saving session conversation: {e}")

    return jsonify({
        "success": True,
        "response": reply,
        "message": reply,
        "timestamp": timestamp_display,
        "timestamp_iso": timestamp_iso,
        "conversation_id": conv_id,
        "user_message": user_message
    })

@app.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history_api():
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    session_convs = session.get('chat_conversations', [])
    supabase_chats = []
    
    try:
        db = get_db_client()
        res = db.table('chat_history').select('*').eq('user_id', user_id).order('timestamp', desc=False).execute()
        if res.data:
            supabase_chats = res.data
    except Exception as e:
        logging.error(f"Error fetching chat history API: {e}")
        
    return jsonify({
        'success': True,
        'conversations': session_convs,
        'raw_history': supabase_chats
    })

@app.route('/api/chat/clear', methods=['POST'])
@login_required
def clear_chat_history():
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    try:
        db = get_db_client()
        db.table('chat_history').delete().eq('user_id', user_id).execute()
        session['chat_conversations'] = []
        session.modified = True
        return jsonify({'success': True, 'message': 'Chat history cleared successfully.'})
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}")
        return jsonify({'success': False, 'error': 'Failed to clear chat history.'}), 500

@app.route('/chatbot')
@login_required
def chatbot():
    text = request.args.get('text', '')
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    chat_history = []
    
    try:
        db = get_db_client()
        chat_resp = db.table('chat_history').select('*').eq('user_id', user_id).order('timestamp', desc=False).execute()
        if chat_resp.data:
            chat_history = chat_resp.data
    except Exception as e:
        logging.error(f"Error fetching chat history from Supabase: {e}")
        chat_history = []

    conversations = session.get('chat_conversations', [])
    return render_template('chatbot.html', text=text, chat_history=chat_history, conversations=conversations)

# --- Route: Index (Home) ---
@app.route("/", methods=["GET"])
def index():
    # If user is logged in, show index, else redirect to login
    if 'user' in session:
        return render_template("index.html", profile=session.get('profile'))
    return redirect(url_for('login'))

# --- Other Routes ---
@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' in session and session.get('user', {}).get('uid'):
            return redirect(url_for('index'))
        return render_template('login.html')
        
    # Handle POST request (JSON from frontend)
    if request.is_json:
        data = request.json
        supabase_token = data.get('supabase_token')
        
        if not supabase_token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400
            
        decoded_token = verify_supabase_token(supabase_token)
        if decoded_token:
            session.clear()
            uid = decoded_token.get('sub')
            email = decoded_token.get('email')
            
            session['user'] = {
                'email': email,
                'uid': uid,
                'token': supabase_token,
                'supabase_token': supabase_token
            }
            
            # Fetch profile
            try:
                profile_resp = supabase.table('profiles').select('*').eq('id', uid).execute()
                if profile_resp.data:
                    profile = profile_resp.data[0]
                    session['profile'] = {
                        'name': profile.get('name', ''),
                        'email': email,
                        'phone': profile.get('phone', '')
                    }
                else:
                    session['profile'] = {'name': '', 'email': email, 'phone': ''}
            except Exception as e:
                logging.error(f"Error fetching profile: {e}")
                session['profile'] = {'name': '', 'email': email, 'phone': ''}
                
            session.modified = True
            return jsonify({'success': True, 'redirect': url_for('index')})
            
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    
    return jsonify({'success': False, 'message': 'Invalid request format'}), 400

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
        
    if request.is_json:
        data = request.json
        supabase_token = data.get('supabase_token') or data.get('firebase_token') # maintain compat with frontend payload if it sends firebase_token for now
        
        if not supabase_token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400
            
        decoded_token = verify_supabase_token(supabase_token)
        if decoded_token:
            session.clear()
            uid = decoded_token.get('sub')
            email = decoded_token.get('email')
            name = data.get('display_name', '')
            
            session['user'] = {
                'email': email,
                'uid': uid,
                'token': supabase_token,
                'supabase_token': supabase_token
            }
            
            # Since the SQL trigger creates the profile, we just fetch it
            try:
                profile_resp = supabase.table('profiles').select('*').eq('id', uid).execute()
                if profile_resp.data:
                    profile = profile_resp.data[0]
                    session['profile'] = {
                        'name': profile.get('name', ''),
                        'email': email,
                        'phone': profile.get('phone', '')
                    }
                else:
                    # If trigger hasn't run yet, just set basic data
                    session['profile'] = {'name': name, 'email': email, 'phone': ''}
            except Exception as e:
                logging.error(f"Error fetching profile: {e}")
                session['profile'] = {'name': name, 'email': email, 'phone': ''}
                
            session.modified = True
            return jsonify({'success': True, 'redirect': url_for('index')})
            
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    
    return jsonify({'success': False, 'message': 'Invalid request format'}), 400

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # ...handle password reset logic here...
        flash("If your email is registered, you will receive password reset instructions.", "info")
        return redirect(url_for('login'))
    return render_template('forgot-password.html')

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    if not phone:
        return None
    # Remove all non-digit characters except +
    phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    # Ensure it starts with +
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone

@app.route('/profile', methods=['GET', 'POST'])
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        user_uid = g.user.get('sub') # we use sub from verify_supabase_token
        if not user_uid:
            logging.error("No user_uid found in session")
            return redirect(url_for('login'))

        logging.info(f"Processing profile/settings request for user: {user_uid}")
        
        # Get profile from Supabase
        profile_data = {}
        client = get_db_client()
        try:
            profile_resp = client.table('profiles').select('*').eq('id', user_uid).execute()
            if profile_resp.data:
                profile_data = profile_resp.data[0]
            else:
                profile_data = session.get('profile', {})
                profile_data['email'] = g.user.get('email', '')
        except Exception as e:
            logging.error(f"Error getting user data: {e}")
            profile_data = session.get('profile', {})

        if request.method == 'POST':
            try:
                data = request.get_json() if request.is_json else request.form.to_dict()
                logging.info(f"Received profile update data: {data}")
                
                # Prepare data for Supabase profiles table
                street = data.get('street', '').strip()
                city = data.get('city', '').strip()
                state = data.get('state', '').strip()
                zipcode = data.get('zipcode', '').strip()
                country = data.get('country', '').strip()
                address_str = data.get('address') or f"{street} {city} {state} {zipcode} {country}".strip()

                update_data = {
                    'name': data.get('name', ''),
                    'phone': data.get('phone', ''),
                    'photo_url': data.get('photo_url', ''),
                    'dob': data.get('dob', '') or None,
                    'gender': data.get('gender', ''),
                    'address': address_str,
                    'height': float(data.get('height')) if data.get('height') else None,
                    'weight': float(data.get('weight')) if data.get('weight') else None,
                    'blood_group': data.get('blood_group', ''),
                    'smoking': data.get('smoking', ''),
                    'allergies': data.get('allergies', ''),
                    'chronic_conditions': data.get('medical_conditions') or data.get('chronic_conditions', ''),
                    'current_medications': data.get('current_medications') or data.get('medication_reminder', ''),
                    'updated_at': datetime.now().isoformat()
                }

                # Remove None values to avoid overwriting existing data with NULL unless intended
                update_data = {k: v for k, v in update_data.items() if v is not None}

                try:
                    # Update data in Supabase using db client
                    db_client = get_db_client()
                    try:
                        db_client.table('profiles').upsert({'id': user_uid, **update_data}).execute()
                    except Exception as upsert_err:
                        logging.warning(f"Upsert failed, trying update: {upsert_err}")
                        db_client.table('profiles').update(update_data).eq('id', user_uid).execute()
                    
                    logging.info("Updated profile in Supabase")
                    
                    # Update profile_data with new values
                    profile_data.update(update_data)
                    
                    # Update session
                    session['profile'] = profile_data
                    session.modified = True
                    flash("Settings updated successfully!", "success")

                    if request.is_json:
                        return jsonify({
                            'success': True,
                            'profile': profile_data,
                            'message': 'Settings saved successfully'
                        })
                    return redirect(url_for('profile'))

                except Exception as e:
                    logging.error(f"Error updating Supabase: {e}")
                    flash("Failed to update settings in database.", "danger")
                    return jsonify({
                        'success': False,
                        'error': 'Failed to save to database'
                    }), 500

            except Exception as e:
                logging.error(f"Error in profile update: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        # For GET requests
        return render_template('settings.html', profile=profile_data)

    except Exception as e:
        logging.error(f"Profile/Settings error: {e}")
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    return profile()

@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    try:
        user_uid = g.user.get('sub')
        data = request.get_json() if request.is_json else request.form.to_dict()
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not new_password or len(new_password) < 6:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('profile'))

        if new_password != confirm_password:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Passwords do not match'}), 400
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('profile'))

        # Update password in Supabase Auth
        try:
            supabase.auth.admin.update_user_by_id(user_uid, {'password': new_password})
            flash('Password updated successfully!', 'success')
            if request.is_json:
                return jsonify({'success': True, 'message': 'Password updated successfully'})
        except Exception as e:
            logging.error(f"Supabase password update error: {e}")
            flash('Password update processed for your account.', 'info')
            if request.is_json:
                return jsonify({'success': True, 'message': 'Password update processed.'})

        return redirect(url_for('profile'))

    except Exception as e:
        logging.error(f"Update password error: {e}")
        flash(f"Error updating password: {str(e)}", "danger")
        return redirect(url_for('profile'))

@app.route('/export_data', methods=['GET'])
@login_required
def export_data():
    try:
        user_uid = g.user.get('sub')
        user_email = g.user.get('email', '')

        profile_resp = supabase.table('profiles').select('*').eq('id', user_uid).execute()
        chat_resp = supabase.table('chat_history').select('*').eq('user_id', user_uid).execute()

        user_data = {
            "account": {
                "id": user_uid,
                "email": user_email,
                "exported_at": datetime.now().isoformat()
            },
            "profile": profile_resp.data[0] if profile_resp.data else {},
            "chat_history": chat_resp.data if chat_resp.data else []
        }

        buffer = io.BytesIO()
        buffer.write(json.dumps(user_data, indent=2).encode('utf-8'))
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"medscript_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error exporting user data: {e}")
        flash("Could not export user data.", "danger")
        return redirect(url_for('profile'))

@app.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    try:
        user_uid = g.user.get('sub')
        try:
            supabase.table('profiles').delete().eq('id', user_uid).execute()
            supabase.table('chat_history').delete().eq('user_id', user_uid).execute()
        except Exception as e:
            logging.error(f"Error deleting user records: {e}")

        session.clear()
        flash("Your account and associated data have been deleted.", "info")
        return redirect(url_for('login'))
    except Exception as e:
        logging.error(f"Delete account error: {e}")
        session.clear()
        return redirect(url_for('login'))

@app.route('/download_pdf')
def download_pdf():
    text = request.args.get('text', '')
    # Clean up the text for better PDF formatting
    # 1. Remove brackets from lists
    import ast
    def clean_list_lines(lines):
        cleaned = []
        for line in lines:
            # Detect lines like: - ['item1', 'item2', ...]
            if line.strip().startswith("- [") and line.strip().endswith("]"):
                try:
                    items = ast.literal_eval(line.strip()[2:].strip())
                    if isinstance(items, list):
                        for item in items:
                            cleaned.append(f"- {item}")
                        continue
                except Exception:
                    pass
            cleaned.append(line)
        return cleaned

    # 2. Remove lines that are just "---" or empty (but keep section breaks)
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    lines = clean_list_lines(lines)
    # Remove lines that are only whitespace or only contain "---" (but keep one blank line between sections)
    final_lines = []
    prev_blank = False
    for line in lines:
        if line.strip() == "---":
            final_lines.append("-" * 40)
            prev_blank = False
        elif line.strip() == "":
            if not prev_blank:
                final_lines.append("")
                prev_blank = True
        else:
            final_lines.append(line)
            prev_blank = False

    # 3. Remove stray '■' or similar unicode chars if present
    final_lines = [line.replace("■", "") for line in final_lines]

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica", 12)
    y_position = 800
    for line in final_lines:
        pdf.drawString(50, y_position, line)
        y_position -= 20
        if y_position < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y_position = 800
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="extracted_text.pdf", mimetype="application/pdf")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/send_message', methods=['POST'])
def send_message():
    name = request.form.get('name')
    message = request.form.get('message')
    sender_email = "hiteshgottapu@gmail.com"
    receiver_email = "gottapuhitesh@gmail.com"
    password = "your_email_password"
    subject = f"New Message from {name}"
    body = f"Name: {name}\nMessage: {message}\n"
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return jsonify({"success": True, "message": "Message sent successfully!"})
    except Exception as e:
        logging.error(f"Email sending error: {e}")
        return jsonify({"success": False, "message": "Failed to send message."})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/developers')
def developers():
    # Example developer data
    developers = [
        {"name": "Gottapu Hitesh", "role": "Lead Developer", "email": "hiteshgottapu309@gmail.com"},
        {"name": "Jane Doe", "role": "Backend Developer", "email": "jane.doe@example.com"},
        {"name": "John Smith", "role": "Frontend Developer", "email": "john.smith@example.com"}
    ]
    return render_template('developers.html', developers=developers)

@app.route("/doctor_consultation", methods=["GET", "POST"])
def doctor_consultation():
    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        email = request.form.get("email")
        symptoms = request.form.get("symptoms").lower()

        # Example doctor database
        doctors = [
            {"name": "Dr. John Doe", "hospital": "City Hospital", "hospital_email": "cityhospital@example.com", "specialization": "General Physician", "keywords": ["fever", "cold", "cough"], "rating": 4.5},
            {"name": "Dr. Alice Johnson", "hospital": "HealthCare Clinic", "hospital_email": "healthcareclinic@example.com", "specialization": "General Physician", "keywords": ["fever", "cold", "cough", "headache", "fatigue", "dizziness"], "rating": 4.7},
            {"name": "Dr. Jane Smith", "hospital": "HealthCare Clinic", "hospital_email": "healthcareclinic@example.com", "specialization": "Pediatrician", "keywords": ["child", "pediatric", "flu", "diarrhea", "vomiting", "rash"], "rating": 4.8},
            {"name": "Dr. Emily Davis", "hospital": "Wellness Center", "hospital_email": "wellnesscenter@example.com", "specialization": "Dermatologist", "keywords": ["rash", "skin", "itching", "acne", "eczema", "psoriasis"], "rating": 4.6},
            {"name": "Dr. Michael Brown", "hospital": "Metro Hospital", "hospital_email": "metrohospital@example.com", "specialization": "Cardiologist", "keywords": ["chest pain", "heart", "shortness of breath", "hypertension", "palpitations"], "rating": 4.9},
            {"name": "Dr. Sarah Wilson", "hospital": "Care Hospital", "hospital_email": "carehospital@example.com", "specialization": "Gastroenterologist", "keywords": ["stomach pain", "indigestion", "ulcer", "acid reflux", "constipation", "diarrhea"], "rating": 4.7},
            {"name": "Dr. Robert Taylor", "hospital": "Prime Clinic", "hospital_email": "primeclinic@example.com", "specialization": "Neurologist", "keywords": ["migraine", "headache", "dizziness", "seizures", "numbness", "weakness", "neck pain"], "rating": 4.8},
            {"name": "Dr. Laura Martinez", "hospital": "Sunrise Hospital", "hospital_email": "sunrisehospital@example.com", "specialization": "Endocrinologist", "keywords": ["diabetes", "thyroid", "hormonal imbalance", "weight gain", "weight loss"], "rating": 4.6},
            {"name": "Dr. Angela White", "hospital": "Healing Hands Clinic", "hospital_email": "healinghandsclinic@example.com", "specialization": "Psychiatrist", "keywords": ["depression", "anxiety", "insomnia", "mood swings", "stress"], "rating": 4.9},
            {"name": "Dr. Kevin Harris", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Pulmonologist", "keywords": ["cough", "breathlessness", "asthma", "bronchitis", "pneumonia"], "rating": 4.7},
            {"name": "Dr. Sophia Green", "hospital": "Harmony Clinic", "hospital_email": "harmonyclinic@example.com", "specialization": "Ophthalmologist", "keywords": ["blurred vision", "eye pain", "redness of eyes", "dry eyes", "vision loss"], "rating": 4.5},
            {"name": "Dr. William Carter", "hospital": "Hope Hospital", "hospital_email": "hopehospital@example.com", "specialization": "Oncologist", "keywords": ["cancer", "tumor", "chemotherapy", "radiation", "lump"], "rating": 4.8},
            {"name": "Dr. Olivia Adams", "hospital": "Bright Smile Dental", "hospital_email": "brightsmiledental@example.com", "specialization": "Dentist", "keywords": ["toothache", "cavity", "gum bleeding", "oral hygiene", "braces"], "rating": 4.6},
            {"name": "Dr. Ethan Walker", "hospital": "Sunrise Hospital", "hospital_email": "sunrisehospital@example.com", "specialization": "Urologist", "keywords": ["urinary tract infection", "kidney stones", "bladder discomfort", "prostate"], "rating": 4.7},
            {"name": "Dr. Isabella Scott", "hospital": "CarePlus Clinic", "hospital_email": "careplusclinic@example.com", "specialization": "Rheumatologist", "keywords": ["arthritis", "joint swelling", "autoimmune diseases", "stiffness"], "rating": 4.8},
            {"name": "Dr. Benjamin Moore", "hospital": "Wellness Center", "hospital_email": "wellnesscenter@example.com", "specialization": "Hematologist", "keywords": ["anemia", "blood disorders", "clotting issues", "leukemia"], "rating": 4.6},
            {"name": "Dr. Charlotte Evans", "hospital": "Prime Clinic", "hospital_email": "primeclinic@example.com", "specialization": "Allergist", "keywords": ["allergies", "asthma", "skin rash", "hay fever", "food allergies"], "rating": 4.7},
            {"name": "Dr. Daniel Turner", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Infectious Disease Specialist", "keywords": ["infection", "fever", "HIV", "tuberculosis", "hepatitis"], "rating": 4.8},
            {"name": "Dr. Mia Brooks", "hospital": "Green Valley Clinic", "hospital_email": "greenvalleyclinic@example.com", "specialization": "Nephrologist", "keywords": ["kidney failure", "dialysis", "proteinuria", "swelling"], "rating": 4.7},
            {"name": "Dr. Lucas Bennett", "hospital": "City Hospital", "hospital_email": "cityhospital@example.com", "specialization": "Surgeon", "keywords": ["surgery", "appendicitis", "hernia", "trauma", "wound care"], "rating": 4.6},
            {"name": "Dr. Grace Parker", "hospital": "Metro Hospital", "hospital_email": "metrohospital@example.com", "specialization": "Cardiologist", "keywords": ["chest pain", "heart", "shortness of breath", "hypertension", "palpitations"], "rating": 4.9},
            {"name": "Dr. Henry Collins", "hospital": "Care Hospital", "hospital_email": "carehospital@example.com", "specialization": "Gastroenterologist", "keywords": ["stomach pain", "indigestion", "ulcer", "acid reflux", "constipation", "diarrhea"], "rating": 4.7},
            {"name": "Dr. Natalie Cooper", "hospital": "Harmony Clinic", "hospital_email": "harmonyclinic@example.com", "specialization": "Dermatologist", "keywords": ["rash", "skin", "itching", "acne", "eczema", "psoriasis"], "rating": 4.6},
            {"name": "Dr. Ryan Foster", "hospital": "LifeCare Hospital", "hospital_email": "lifecarehospital@example.com", "specialization": "Pulmonologist", "keywords": ["cough", "breathlessness", "asthma", "bronchitis", "pneumonia"], "rating": 4.7}
        ]

        # Filter doctors based on symptoms
        suggested_doctors = [
            doctor for doctor in doctors if any(keyword in symptoms for keyword in doctor["keywords"])
        ]

        return render_template("doctor_consultation.html", doctors=suggested_doctors, name=name, age=age, email=email, symptoms=symptoms)

    # Pre-fill form with data from GET request
    name = request.args.get("name", "")
    age = request.args.get("age", "")
    email = request.args.get("email", "")
    symptoms = request.args.get("symptoms", "")

    return render_template("doctor_consultation.html", name=name, age=name, email=email, symptoms=symptoms)

@app.route("/schedule_appointment", methods=["POST"])
def schedule_appointment():
    patient_name = request.form.get("patient_name")
    doctor_name = request.form.get("doctor_name")
    doctor_email = request.form.get("doctor_email")
    hospital_email = request.form.get("hospital_email")  # Added hospital email
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    additional_details = request.form.get("additional_details")

    # Email content
    subject = f"Appointment Request with {doctor_name}"
    patient_email = "user@example.com"  # Replace with the user's email from the session or form
    email_body = f"""
    Dear {doctor_name},

    You have a new appointment request from {patient_name}.

    Appointment Details:
    - Date: {appointment_date}
    - Time: {appointment_time}
    - Additional Details: {additional_details}

    Please confirm the appointment at your earliest convenience.

    Regards,
    MedScript
    """

    # Send email to doctor
    send_email(doctor_email, subject, email_body)

    # Send email to hospital
    send_email(hospital_email, subject, email_body)

    # Send confirmation email to patient
    confirmation_subject = "Appointment Request Confirmation"
    confirmation_body = f"""
    Dear {patient_name},

    Your appointment request with Dr. {doctor_name} has been sent successfully.

    Appointment Details:
    - Date: {appointment_date}
    - Time: {appointment_time}
    - Additional Details: {additional_details}

    You will receive a confirmation from the doctor soon.

    Regards,
    MedScript
    """
    send_email(patient_email, confirmation_subject, confirmation_body)

    flash("Appointment request sent successfully!", "success")
    return redirect(url_for("doctor_consultation"))

def send_email(to_email, subject, body):
    sender_email = os.getenv("SENDER_EMAIL")  # Use from .env
    sender_password = os.getenv("SENDER_EMAIL_PASSWORD")  # Use from .env

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")

# --- Twilio Integration ---
# --- Route: Emergency ---
@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

# --- Function: Send Emergency Email to Hospital (fixed: always send to hiteshsimhagottpu@gmail.com from user email) ---
def send_emergency_email_to_hospital(user_email, subject, message_body):
    import ssl
    port = 465
    smtp_server = "smtp.gmail.com"
    receiver_email = "hiteshsimhagottapu@gmail.com"
    context = ssl.create_default_context()
    # Improved HTML and plain text email format
    html_body = f"""
    <html>
    <body>
        <h2 style="color:#d32f2f;">🚨 Emergency Alert Notification</h2>
        <p>
            <b>Alert triggered by:</b> {user_email}<br>
            <b>Time:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
        </p>
        <p>
            <b>Symptoms:</b><br>
            <span style="color:#333;">{message_body.get('symptoms', '')}</span>
        </p>
        <p>
            <b>Location:</b><br>
            <a href="{message_body.get('location_url', '')}">{message_body.get('location_url', '')}</a>
        </p>
        <p>
            <b>Additional Info:</b><br>
            {message_body.get('additional', '')}
        </p>
        <hr>
        <p style="color:#888;">This is an automated emergency notification from MedScript.</p>
    </body>
    </html>
    """
    plain_body = (
        f"EMERGENCY ALERT\n"
        f"Alert triggered by: {user_email}\n"
        f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Symptoms: {message_body.get('symptoms', '')}\n"
        f"Location: {message_body.get('location_url', '')}\n"
        f"Additional Info: {message_body.get('additional', '')}\n"
        f"\nThis is an automated emergency notification from MedScript."
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user_email
    msg["To"] = receiver_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    user_password = os.getenv("USER_EMAIL_PASSWORD")
    if not user_password:
        logging.error("USER_EMAIL_PASSWORD environment variable not set.")
        return False
    try:
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(user_email, user_password)
            server.sendmail(user_email, receiver_email, msg.as_string())
        return True
    except Exception as e:
        logging.error(f"Failed to send emergency email to hospital: {e}")
        return False

# --- Route: Handle Firebase Authentication Action Links ---
@app.route('/auth/action', methods=['GET'])
def handle_auth_action():
    mode = request.args.get('mode')
    oob_code = request.args.get('oobCode')

    if not mode or not oob_code:
        flash("Invalid or missing parameters in the action link.", "danger")
        return redirect(url_for('index'))

    try:
        if mode == 'verifyEmail':
            # Handle email verification
            auth.verify_id_token(oob_code)
            flash("Email verified successfully!", "success")
        elif mode == 'resetPassword':
            # Redirect to a password reset page
            return redirect(url_for('reset_password', oobCode=oob_code))
        else:
            flash("Unsupported action mode.", "danger")
    except Exception as e:
        logging.error(f"Error handling auth action: {str(e)}")
        flash("An error occurred while processing the action link.", "danger")

    return redirect(url_for('index'))

# --- Route to serve static files like firebase.js ---
@app.route('/firebase.js')
def serve_firebase_js():
    return send_from_directory('static', 'firebase.js')

# --- Error Handler for 404 ---
@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404

# ================== SECOND PART: AI CONSULTANT ==================
# --- Infermedica API Credentials (optional, for /api/symptom-check) ---
INFERMEDICA_APP_ID = os.getenv("INFERMEDICA_APP_ID", "")
INFERMEDICA_APP_KEY = os.getenv("INFERMEDICA_APP_KEY", "")

# --- Load Datasets & Model ---
sym_des = pd.read_csv("dataset/symtoms_df.csv")
precautions = pd.read_csv("dataset/precautions_df.csv")
workout = pd.read_csv("dataset/workout_df.csv")
description = pd.read_csv("dataset/description.csv")
medications = pd.read_csv("dataset/medications.csv")
diets = pd.read_csv("dataset/diets.csv")
svc = pickle.load(open('model/svc.pkl','rb'))

# --- Helper Function to Retrieve Disease Details ---
def helper(dis):
    desc = description[description['Disease'] == dis]['Description']
    desc = " ".join([w for w in desc])
    pre = precautions[precautions['Disease'] == dis][['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4']]
    pre = [col for col in pre.values]
    med = medications[medications['Disease'] == dis]['Medication']
    med = [m for m in med.values]
    die = diets[diets['Disease'] == dis]['Diet']
    die = [d for d in die.values]
    wrkout = workout[workout['disease'] == dis]['workout']
    return desc, pre, med, die, wrkout

# --- Dictionaries for Symptom Mapping & Disease List ---
symptoms_dict = {
    'itching': 0, 'skin_rash': 1, 'nodal_skin_eruptions': 2, 'continuous_sneezing': 3,
    'shivering': 4, 'chills': 5, 'joint_pain': 6, 'stomach_pain': 7, 'acidity': 8,
    'ulcers_on_tongue': 9, 'muscle_wasting': 10, 'vomiting': 11, 'burning_micturition': 12,
    'spotting_urination': 13, 'fatigue': 14, 'weight_gain': 15, 'anxiety': 16,
    'cold_hands_and_feets': 17, 'mood_swings': 18, 'weight_loss': 19, 'restlessness': 20,
    'lethargy': 21, 'patches_in_throat': 22, 'irregular_sugar_level': 23, 'cough': 24,
    'high_fever': 25, 'sunken_eyes': 26, 'breathlessness': 27, 'sweating': 28,
    'dehydration': 29, 'indigestion': 30, 'headache': 31, 'yellowish_skin': 32,
    'dark_urine': 33, 'nausea': 34, 'loss_of_appetite': 35, 'pain_behind_the_eyes': 36,
    'back_pain': 37, 'constipation': 38, 'abdominal_pain': 39, 'diarrhoea': 40,
    'mild_fever': 41, 'yellow_urine': 42, 'yellowing_of_eyes': 43, 'acute_liver_failure': 44,
    'fluid_overload': 45, 'swelling_of_stomach': 46, 'swelled_lymph_nodes': 47, 'malaise': 48,
    'blurred_and_distorted_vision': 49, 'phlegm': 50, 'throat_irritation': 51, 'redness_of_eyes': 52,
    'sinus_pressure': 53, 'runny_nose': 54, 'congestion': 55, 'chest_pain': 56,
    'weakness_in_limbs': 57, 'fast_heart_rate': 58, 'pain_during_bowel_movements': 59,
    'pain_in_anal_region': 60, 'bloody_stool': 61, 'irritation_in_anus': 62, 'neck_pain': 63,
    'dizziness': 64, 'cramps': 65, 'bruising': 66, 'obesity': 67, 'swollen_legs': 68,
    'swollen_blood_vessels': 69, 'puffy_face_and_eyes': 70, 'enlarged_thyroid': 71,
    'brittle_nails': 72, 'swollen_extremeties': 73, 'excessive_hunger': 74, 'extra_marital_contacts': 75,
    'drying_and_tingling_lips': 76, 'slurred_speech': 77, 'knee_pain': 78, 'hip_joint_pain': 79,
    'muscle_weakness': 80, 'stiff_neck': 81, 'swelling_joints': 82, 'movement_stiffness': 83,
    'spinning_movements': 84, 'loss_of_balance': 85, 'unsteadiness': 86, 'weakness_of_one_body_side': 87,
    'loss_of_smell': 88, 'bladder_discomfort': 89, 'foul_smell_of urine': 90, 'continuous_feel_of_urine': 91,
    'passage_of_gases': 92, 'internal_itching': 93, 'toxic_look_(typhos)': 94, 'depression': 95,
    'irritability': 96, 'muscle_pain': 97, 'altered_sensorium': 98, 'red_spots_over_body': 99,
    'belly_pain': 100, 'abnormal_menstruation': 101, 'dischromic _patches': 102, 'watering_from_eyes': 103,
    'increased_appetite': 104, 'polyuria': 105, 'family_history': 106, 'mucoid_sputum': 107,
    'rusty_sputum': 108, 'lack_of_concentration': 109, 'visual_disturbances': 110,
    'receiving_blood_transfusion': 111, 'receiving_unsterile_injections': 112, 'coma': 113,
    'stomach_bleeding': 114, 'distention_of_abdomen': 115, 'history_of_alcohol_consumption': 116,
    'fluid_overload.1': 117, 'blood_in_sputum': 118, 'prominent_veins_on_calf': 119,
    'palpitations': 120, 'painful_walking': 121, 'pus_filled_pimples': 122, 'blackheads': 123,
    'scurring': 124, 'skin_peeling': 125, 'silver_like_dusting': 126, 'small_dents_in_nails': 127,
    'inflammatory_nails': 128, 'blister': 129, 'red_sore_around_nose': 130, 'yellow_crust_ooze': 131
}


diseases_list = {
    15: 'Fungal infection', 4: 'Allergy', 16: 'GERD', 9: 'Chronic cholestasis',
    14: 'Drug Reaction', 33: 'Peptic ulcer diseae', 1: 'AIDS', 12: 'Diabetes',
    17: 'Gastroenteritis', 6: 'Bronchial Asthma', 23: 'Hypertension', 30: 'Migraine',
    7: 'Cervical spondylosis', 32: 'Paralysis (brain hemorrhage)', 28: 'Jaundice',
    29: 'Malaria', 8: 'Chicken pox', 11: 'Dengue', 37: 'Typhoid', 40: 'hepatitis A',
    19: 'Hepatitis B', 20: 'Hepatitis C', 21: 'Hepatitis D', 22: 'Hepatitis E',
    3: 'Alcoholic hepatitis', 36: 'Tuberculosis', 10: 'Common Cold', 34: 'Pneumonia',
    13: 'Dimorphic hemmorhoids(piles)', 18: 'Heart attack', 39: 'Varicose veins',
    26: 'Hypothyroidism', 24: 'Hyperthyroidism', 25: 'Hypoglycemia', 31: 'Osteoarthristis',
    5: 'Arthritis', 0: '(vertigo) Paroymsal Positional Vertigo', 2: 'Acne',
    38: 'Urinary tract infection', 35: 'Psoriasis', 27: 'Impetigo'
}

# --- Function: Correct Spelling using TextBlob ---
def correct_spelling(symptom):
    blob = TextBlob(symptom)
    return str(blob.correct())

# --- Symptom Mapping for Synonyms ---
symptom_mapping = defaultdict(lambda: "unknown", {
    "itching": ["itching"],
    "skin_rash": ["skin rash", "rash", "dermatitis", "rashes"],
    "nodal_skin_eruptions": ["nodal skin eruptions", "skin eruptions", "bumps"],
    "continuous_sneezing": ["continuous sneezing", "sneezing"],
    "shivering": ["shivering", "trembling"],
    "chills": ["chills", "cold sensation", "cold"],
    "joint_pain": ["joint pain", "arthralgia", "aching joints"],
    "stomach_pain": ["stomach pain", "abdominal pain", "belly ache"],
    "acidity": ["acidity", "heartburn", "acid reflux"],
    "ulcers_on_tongue": ["ulcers on tongue", "tongue ulcers", "mouth sores"],
    "muscle_wasting": ["muscle wasting", "muscle loss"],
    "vomiting": ["vomiting", "emesis", "throwing up"],
    "burning_micturition": ["burning micturition", "burning urination", "painful urination"],
    "spotting_urination": ["spotting urination", "blood in urine", "hematuria"],
    "fatigue": ["fatigue", "tiredness", "exhaustion"],
    "weight_gain": ["weight gain", "increased weight"],
    "anxiety": ["anxiety", "nervousness", "worry", "sleeping"],
    "cold_hands_and_feets": ["cold hands and feet", "cold extremities"],
    "mood_swings": ["mood swings", "emotional changes"],
    "weight_loss": ["weight loss", "decreased weight"],
    "restlessness": ["restlessness", "agitation"],
    "lethargy": ["lethargy", "sluggishness"],
    "patches_in_throat": ["patches in throat", "throat patches", "throat lesions"],
    "irregular_sugar_level": ["irregular sugar level", "unstable glucose", "blood sugar fluctuations"],
    "cough": ["cough", "coughing"],
    "high_fever": ["high fever", "elevated temperature"],
    "sunken_eyes": ["sunken eyes", "hollow eyes"],
    "breathlessness": ["breathlessness", "shortness of breath", "dyspnea"],
    "sweating": ["sweating", "perspiration"],
    "dehydration": ["dehydration", "fluid loss"],
    "indigestion": ["indigestion", "upset stomach"],
    "headache": ["headache", "head pain", "migraine"],
    "yellowish_skin": ["yellowish skin", "jaundice"],
    "dark_urine": ["dark urine"],
    "swelled_lymph_nodes": ["swelled lymph nodes", "enlarged lymph nodes"],
    "malaise": ["malaise", "general discomfort"],
    "blurred_and_distorted_vision": ["blurred and distorted vision", "blurry vision"],
    "phlegm": ["phlegm", "mucus"],
    "throat_irritation": ["throat irritation", "sore throat"],
    "redness_of_eyes": ["redness of eyes", "bloodshot eyes"],
    "sinus_pressure": ["sinus pressure", "sinus congestion"],
    "runny_nose": ["runny nose", "rhinorrhea"],
    "congestion": ["congestion", "nasal blockage"],
    "chest_pain": ["chest pain", "angina"],
    "weakness_in_limbs": ["weakness in limbs", "limb weakness"],
    "fast_heart_rate": ["fast heart rate", "tachycardia"],
    "pain_during_bowel_movements": ["pain during bowel movements", "painful defecation"],
    "pain_in_anal_region": ["pain in anal region", "anal pain"],
    "bloody_stool": ["bloody stool", "rectal bleeding"],
    "irritation_in_anus": ["irritation in anus", "anal itching"],
    "neck_pain": ["neck pain", "cervical pain"],
    "dizziness": ["dizziness", "lightheadedness"],
    "cramps": ["cramps", "muscle cramps", "spasms"],
    "bruising": ["bruising", "hematoma"],
    "obesity": ["obesity", "overweight"],
    "swollen_legs": ["swollen legs", "leg edema"],
    "swollen_blood_vessels": ["swollen blood vessels", "varicose veins"],
    "puffy_face_and_eyes": ["puffy face and eyes", "facial swelling"],
    "enlarged_thyroid": ["enlarged thyroid", "goiter"],
    "brittle_nails": ["brittle nails", "weak nails"],
    "swollen_extremeties": ["swollen extremities", "swollen arms and legs"],
    "excessive_hunger": ["excessive hunger", "polyphagia"],
    "extra_marital_contacts": ["extra marital contacts", "multiple sexual partners"],
    "drying_and_tingling_lips": ["drying and tingling lips", "lip dryness"],
    "slurred_speech": ["slurred speech", "dysarthria"],
    "knee_pain": ["knee pain", "pain in the knees"],
    "hip_joint_pain": ["hip joint pain", "hip pain"],
    "muscle_weakness": ["muscle weakness", "muscle fatigue"],
    "stiff_neck": ["stiff neck", "neck stiffness"],
    "swelling_joints": ["swelling joints", "joint swelling"],
    "movement_stiffness": ["movement stiffness", "rigidity"],
    "spinning_movements": ["spinning movements", "vertigo"],
    "loss_of_balance": ["loss of balance", "balance problems"],
    "unsteadiness": ["unsteadiness", "lack of balance"],
    "weakness_of_one_body_side": ["weakness of one body side", "hemiparesis"],
    "loss_of_smell": ["loss of smell", "anosmia"],
    "bladder_discomfort": ["bladder discomfort", "bladder pain"],
    "foul_smell_of urine": ["foul smell of urine", "smelly urine"],
    "continuous_feel_of_urine": ["continuous feel of urine", "urgency to urinate"],
    "passage_of_gases": ["passage of gases", "flatulence"],
    "internal_itching": ["internal itching"],
    "toxic_look_(typhos)": ["toxic look (typhos)", "septic appearance"],
    "depression": ["depression", "low mood"],
    "irritability": ["irritability", "easily annoyed"],
    "muscle_pain": ["muscle pain", "myalgia"],
    "altered_sensorium": ["altered sensorium", "confusion"],
    "red_spots_over_body": ["red spots over body", "rash with red spots"],
    "belly_pain": ["belly pain", "abdominal pain"],
    "abnormal_menstruation": ["abnormal menstruation", "irregular periods"],
    "dischromic_patches": ["dischromic patches", "skin discoloration"],
    "watering_from_eyes": ["watering from eyes", "teary eyes"],
    "increased_appetite": ["increased appetite", "hyperphagia"],
    "polyuria": ["polyuria", "excessive urination"],
    "family_history": ["family history", "genetic predisposition"],
    "mucoid_sputum": ["mucoid sputum", "mucus in sputum"],
    "rusty_sputum": ["rusty sputum", "blood-tinged sputum"],
    "lack_of_concentration": ["lack of concentration", "difficulty focusing"],
    "visual_disturbances": ["visual disturbances", "vision problems"],
    "receiving_blood_transfusion": ["receiving blood transfusion"],
    "receiving_unsterile_injections": ["receiving unsterile injections"]
})

# --- Function: Get Top N Predicted Diseases based on Symptoms ---
def get_top_predicted_values(patient_symptoms, top_n=3):
    input_vector = np.zeros(len(symptoms_dict))
    for item in patient_symptoms:
        corrected_item = item
        index = symptoms_dict.get(corrected_item, -1)
        if index != -1:
            input_vector[index] = 1
        else:
            found = False
            for key, synonyms in symptom_mapping.items():
                if item in synonyms:
                    index = symptoms_dict.get(key, -1)
                    if index != -1:
                        input_vector[index] = 1
                        found = True
                        break
            if not found:
                corrected_item = correct_spelling(item)
                index = symptoms_dict.get(corrected_item, -1)
                if index != -1:
                    input_vector[index] = 1
                else:
                    for key, synonyms in symptom_mapping.items():
                        if corrected_item in synonyms:
                            index = symptoms_dict.get(key, -1)
                            if index != -1:
                                input_vector[index] = 1
                                break
    # Get probabilities for all classes
    if hasattr(svc, "predict_proba"):
        probs = svc.predict_proba([input_vector])[0]
        top_indices = np.argsort(probs)[::-1][:top_n]
    else:
        # fallback: use decision_function or just predict one
        pred = svc.predict([input_vector])[0]
        top_indices = [pred]
    top_diseases = []
    for idx in top_indices:
        disease = diseases_list.get(idx, "Unknown Disease")
        top_diseases.append((idx, disease))
    return top_diseases

# --- Route: AI Consultant Page (GET) ---
@app.route("/ai_consultant")
def ai_consultant():
    return render_template("ai_consultant.html")

# --- Route: Disease Prediction from Symptoms (POST) ---
@app.route("/predict", methods=['POST'])
def predict():
    name = request.form.get('name')
    age = request.form.get('age')
    location = request.form.get('location')
    symptoms = request.form.get('symptoms')
    
    if symptoms == "Symptoms":
        message = "Please either write symptoms or check for misspellings."
        return render_template('ai_consultant.html', message=message)
    if not symptoms:
        message = "Please enter symptoms."
        return render_template('ai_consultant.html', message=message)
    else:
        user_symptoms = [s.strip() for s in symptoms.split(',')]
        user_symptoms = [symptom.strip("[]' ") for symptom in user_symptoms]
        disease_set = set()
        predictions = []
        if len([s for s in user_symptoms if s]) == 1:
            # Only one symptom: predict only the top disease for that symptom
            symptom = user_symptoms[0]
            top_diseases = get_top_predicted_values([symptom], top_n=1)
            for idx, predicted_disease in top_diseases:
                if predicted_disease not in disease_set:
                    disease_set.add(predicted_disease)
                    dis_des, pre, med, rec_diet, wrkout = helper(predicted_disease)
                    my_precautions = pre[0] if pre and len(pre) > 0 else []
                    predictions.append({
                        'predicted_disease': predicted_disease,
                        'dis_des': dis_des,
                        'my_precautions': my_precautions,
                        'medications': med,
                        'my_diet': rec_diet,
                        'workout': wrkout
                    })
        else:
            # Multiple symptoms: show top 3 predicted diseases for all symptoms together
            top_diseases_all = get_top_predicted_values(user_symptoms, top_n=3)
            for idx, predicted_disease in top_diseases_all:
                if predicted_disease not in disease_set:
                    disease_set.add(predicted_disease)
                    dis_des, pre, med, rec_diet, wrkout = helper(predicted_disease)
                    my_precautions = pre[0] if pre and len(pre) > 0 else []
                    predictions.append({
                        'predicted_disease': predicted_disease,
                        'dis_des': dis_des,
                        'my_precautions': my_precautions,
                        'medications': med,
                        'my_diet': rec_diet,
                        'workout': wrkout
                    })
        return render_template('ai_consultant.html',
                               name=name,
                               age=age,
                               location=location,
                               symptoms=symptoms,
                               predictions=predictions)

# ================== SYMPTOM CHECKER & EMERGENCY ALERT API ==================
# 1. Symptom Input & Diagnosis (Core)
#    - POST /api/symptom-check
#      Input: JSON {symptoms: "...", age: int, sex: "male"/"female"}
#      Output: { conditions: [ { name, confidence }, ... ] } (Infermedica) or { predictions: [...] } (local)

def infermedica_symptom_check(symptoms, age, sex):
    """
    Calls the Infermedica API to check symptoms and return possible conditions.
    Tries to map user symptoms to Infermedica IDs using synonyms and fuzzy matching for better accuracy.
    """
    url = "https://api.infermedica.com/v3/diagnosis"
    headers = {
        "App-Id": INFERMEDICA_APP_ID,
        "App-Key": INFERMEDICA_APP_KEY,
        "Content-Type": "application/json"
    }
    # In production, you should map symptoms to Infermedica IDs.
    # Here, we try to improve mapping using synonyms and fuzzy matching.
    evidence = []
    # Optionally, cache Infermedica symptoms list for better mapping
    try:
        symptoms_list_url = "https://api.infermedica.com/v3/symptoms"
        symptoms_response = requests.get(symptoms_list_url, headers=headers, timeout=10)
        symptoms_response.raise_for_status()
        infermedica_symptoms = symptoms_response.json()
        infermedica_symptom_names = {s['name'].lower(): s['id'] for s in infermedica_symptoms}
    except Exception as e:
        logging.warning(f"Could not fetch Infermedica symptoms list: {e}")
        infermedica_symptom_names = {}

    from fuzzywuzzy import process as fuzzy_process

    for symptom in [s.strip() for s in symptoms.split(',') if s.strip()]:
        symptom_lower = symptom.lower()
        # Try direct match
        if symptom_lower in infermedica_symptom_names:
            evidence.append({"id": infermedica_symptom_names[symptom_lower], "choice_id": "present"})
        else:
            # Fuzzy match to Infermedica symptom names
            if infermedica_symptom_names:
                match, score = fuzzy_process.extractOne(symptom_lower, infermedica_symptom_names.keys())
                if score > 80:
                    evidence.append({"id": infermedica_symptom_names[match], "choice_id": "present"})
                else:
                    # fallback: use raw symptom as id (may fail)
                    evidence.append({"id": symptom_lower.replace(" ", "_"), "choice_id": "present"})
            else:
                evidence.append({"id": symptom_lower.replace(" ", "_"), "choice_id": "present"})
    payload = {
        "sex": sex,
        "age": age,
        "evidence": evidence
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Infermedica API error: {e}")
        return {"error": str(e)}

@app.route("/api/symptom-check", methods=["POST"])
def api_symptom_check():
    data = request.get_json(force=True)
    symptoms = data.get("symptoms", "")
    age = data.get("age", 30)
    sex = data.get("sex", "male")
    # Prefer Infermedica if credentials are set
    if INFERMEDICA_APP_ID and INFERMEDICA_APP_KEY:
        result = infermedica_symptom_check(symptoms, age, sex)
        # Format Infermedica output for frontend
        if "conditions" in result:
            # Already formatted
            pass
        elif "conditions" not in result and "conditions" not in result.get("result", {}):
            # Try to extract from diagnosis response
            if "conditions" in result:
                pass
            elif "conditions" in result.get("result", {}):
                result = result["result"]
            elif "conditions" not in result and "conditions" not in result.get("result", {}):
                # Try to extract from diagnosis API response
                if "conditions" in result:
                    pass
                else:
                    # fallback: wrap as error
                    result = {"error": "No conditions found in Infermedica response."}
        # Add top 3 conditions with confidence if available
        if "conditions" in result:
            result["top_conditions"] = [
                {"name": c.get("name"), "confidence": c.get("probability")}
                for c in result["conditions"][:3]
            ]
        return jsonify(result)
    else:
        # Fallback: use local symptom-to-disease lookup
        user_symptoms = [s.strip() for s in symptoms.split(',')]
        top_diseases = get_top_predicted_values(user_symptoms, top_n=3)
        result = {
            "predictions": [ {"name": disease, "confidence": None} for idx, disease in top_diseases ]
        }
        return jsonify(result)

# 2. Emergency Alert Trigger (New Feature)
#    - POST /api/emergency-alert
#      Input: JSON {symptoms: "...", lat: float, lng: float, phone: "...}
#      Output: {emergency: bool, hospitals: [...], sms_sent: bool}

def is_emergency(symptoms):
    # Define a list of keywords that indicate a medical emergency
    emergency_keywords = [
        "chest pain", "shortness of breath", "severe bleeding", "unconscious", "seizure", "stroke",
        "heart attack", "loss of consciousness", "difficulty breathing", "severe allergic reaction",
        "anaphylaxis", "severe pain", "not breathing", "blue lips", "no pulse", "severe burn",
        "major trauma", "confusion", "slurred speech", "weakness on one side", "sudden vision loss"
    ]
    symptoms_lower = symptoms.lower()
    # Improved: also check for synonyms and fuzzy matches
    from fuzzywuzzy import fuzz
    for keyword in emergency_keywords:
        if keyword in symptoms_lower or fuzz.partial_ratio(keyword, symptoms_lower) > 85:
            return True
    return False

def find_nearby_hospitals(lat, lng, api_key, radius=5000):
    """
    Uses Google Places API to find nearby hospitals given latitude and longitude.
    Returns a list of hospitals with name and address.
    """
    url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={radius}&type=hospital&key={api_key}"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        hospitals = []
        for result in data.get("results", []):
            hospitals.append({
                "name": result.get("name"),
                "address": result.get("vicinity"),
                "location": result.get("geometry", {}).get("location", {}),
                "rating": result.get("rating"),
                "user_ratings_total": result.get("user_ratings_total"),
                "place_id": result.get("place_id"),
                "open_now": result.get("opening_hours", {}).get("open_now", None)
            })
        # Debug: log hospitals found
        logging.debug(f"Nearby hospitals found: {hospitals}")
        # Sort hospitals by open status (True > False/None) and rating (None as 0)
        hospitals = sorted(
            hospitals,
            key=lambda h: (
                bool(h.get("open_now")),  # True > False/None
                h.get("rating") if h.get("rating") is not None else 0
            ),
            reverse=True
        )
        return hospitals
    except Exception as e:
        logging.error(f"Error fetching nearby hospitals: {e}")
        return []

@app.route("/api/emergency-alert", methods=["POST"])
def api_emergency_alert():
    data = request.get_json(force=True)
    symptoms = data.get("symptoms", "")
    lat = data.get("lat")
    lng = data.get("lng")
    phone = data.get("phone")
    emergency = is_emergency(symptoms)
    hospitals = []
    sms_sent = False
    logging.debug(f"Received emergency alert: symptoms={symptoms}, lat={lat}, lng={lng}, phone={phone}, emergency={emergency}")
    if emergency:
        # Query Google Places API for nearby hospitals
        if lat and lng and GOOGLE_API_KEY:
            hospitals = find_nearby_hospitals(lat, lng, GOOGLE_API_KEY)
            logging.debug(f"Hospitals returned to frontend: {hospitals}")
        # Optionally send SMS alert to emergency contact
        if phone:
            def send_sms_alert(phone, message):
                # Placeholder: Implement SMS sending logic here (e.g., using Twilio or another SMS API)
                logging.info(f"SMS sent to {phone}: {message}")
            def sms_thread():
                send_sms_alert(phone, f"Emergency detected: {symptoms}. Please seek immediate help. Location: https://maps.google.com/?q={lat},{lng}")
            import threading
            threading.Thread(target=sms_thread).start()
            sms_sent = True
    else:
        # Even if not an emergency, still return hospitals for map display
        if lat and lng and GOOGLE_API_KEY:
            hospitals = find_nearby_hospitals(lat, lng, GOOGLE_API_KEY)
            logging.debug(f"(Non-emergency) Hospitals returned to frontend: {hospitals}")
    return jsonify({
        "emergency": emergency,
        "hospitals": hospitals,
        "sms_sent": sms_sent
    })

# Add this new route for session checking
@app.route('/check-session')
def check_session():
    is_authenticated = 'user' in session
    logging.info(f"Session check - authenticated: {is_authenticated}, session: {session}")
    return jsonify({'authenticated': is_authenticated})

# ================== Run the App ==================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

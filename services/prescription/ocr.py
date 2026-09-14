"""
MedScript Prescription OCR & Clinical Analysis Service
"""

import os
import io
import base64
import logging
import requests
from PIL import Image
from config import get_config
from .generator import parse_prescription_response, build_clean_transcript

config = get_config()


def extract_text_from_image(file):
    """
    Extract and structure clinical text from a prescription image.
    Uses Gemini Vision API primary, falling back to Google Cloud Vision.
    """
    try:
        # Read and prepare image
        image_bytes = file.read()
        file.seek(0)

        # Handle PDF uploads if pdf2image is present
        mime_type = getattr(file, "content_type", "image/jpeg") or "image/jpeg"
        if file.filename and file.filename.lower().endswith(".pdf"):
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(image_bytes)
                if images:
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format='JPEG')
                    image_bytes = img_byte_arr.getvalue()
                    mime_type = "image/jpeg"
            except Exception as e:
                logging.warning(f"Could not convert PDF to image: {e}")

        # Compress if larger than 4MB
        if len(image_bytes) > 4 * 1024 * 1024:
            try:
                pil_img = Image.open(io.BytesIO(image_bytes))
                pil_img.thumbnail((1800, 1800))
                out_io = io.BytesIO()
                pil_img.save(out_io, format='JPEG', quality=85)
                image_bytes = out_io.getvalue()
                mime_type = "image/jpeg"
            except Exception as e:
                logging.warning(f"Image compression failed: {e}")

        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # 1. Primary: Gemini Multimodal Vision API
        api_key = config.GEMINI_API_KEY or config.GOOGLE_API_KEY
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

            models = [config.GEMINI_MODEL, "gemini-1.5-flash", "gemini-2.0-flash"]
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
                                    {"inline_data": {"mime_type": mime_type, "data": base64_image}}
                                ]
                            }
                        ]
                    }
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
                except Exception as e:
                    logging.error(f"Error calling Gemini Vision model {model_name}: {e}")
                    continue

        # 2. Fallback: Google Cloud Vision
        if config.GOOGLE_API_KEY:
            try:
                gvision_url = f'https://vision.googleapis.com/v1/images:annotate?key={config.GOOGLE_API_KEY}'
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

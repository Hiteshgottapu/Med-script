"""
MedScript AI Clinical Chatbot Service
======================================
Handles:
- Gemini API communication with retry and model fallback
- Healthcare safety protocols and system instructions
- Multi-turn conversation history management
- Supabase chat history persistence
- Session thread synchronization
"""

import os
import time
import logging
import requests
from datetime import datetime
from config import get_config
from services.auth import get_db_client

config = get_config()

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


class MedicalChatbotService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY or config.GOOGLE_API_KEY
        self.primary_model = config.GEMINI_MODEL
        self.fallback_models = [
            self.primary_model,
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        # Deduplicate
        seen = set()
        self.models = [m for m in self.fallback_models if m and not (m in seen or seen.add(m))]

    def generate_response(self, prompt, history=None):
        """Generate response from Gemini with fallback models."""
        if not prompt or not prompt.strip():
            return "Please enter a question or message to begin."

        contents = []
        if history and isinstance(history, list):
            for msg in history:
                role = msg.get("role")
                content = msg.get("content") or msg.get("text") or ""
                if isinstance(content, list):
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

        if not self.api_key:
            return "AI Assistant configuration error: Missing Gemini API key in environment."

        headers = {"Content-Type": "application/json"}

        for model_name in self.models:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            params = {"key": self.api_key}
            try:
                logging.info(f"Sending chat request to Gemini model '{model_name}' (turns: {len(contents)})")
                response = requests.post(api_url, params=params, headers=headers, json=payload, timeout=25)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        parts = candidates[0]["content"]["parts"]
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                logging.warning(f"Model {model_name} returned status {response.status_code}")
            except requests.exceptions.Timeout:
                logging.error(f"Timeout calling Gemini model '{model_name}'")
                continue
            except Exception as e:
                logging.error(f"Error calling Gemini model '{model_name}': {e}")
                continue

        return "The assistant is temporarily unavailable. Please check your connection and try again in a few moments."

    def save_chat_to_supabase(self, user_id, user_message, bot_response):
        """Save chat entry to Supabase database if available."""
        if not user_id:
            return False
        try:
            db = get_db_client()
            if not db:
                return False
            timestamp_iso = datetime.now().isoformat()
            chat_entry = {
                'user_id': user_id,
                'user_message': user_message,
                'bot_response': bot_response,
                'timestamp': timestamp_iso
            }
            # Check duplicate
            recent = db.table('chat_history').select('*').eq('user_id', user_id).order('timestamp', desc=True).limit(1).execute()
            if recent.data:
                last = recent.data[0]
                if last.get('user_message') == user_message and last.get('bot_response') == bot_response:
                    return True
            db.table('chat_history').insert(chat_entry).execute()
            return True
        except Exception as e:
            logging.error(f"Error saving chat to Supabase: {e}")
            return False

    def get_user_chat_history(self, user_id):
        """Fetch saved chats from Supabase."""
        if not user_id:
            return []
        try:
            db = get_db_client()
            if not db:
                return []
            res = db.table('chat_history').select('*').eq('user_id', user_id).order('timestamp', desc=False).execute()
            return res.data or []
        except Exception as e:
            logging.error(f"Error retrieving chat history: {e}")
            return []

    def clear_user_chat_history(self, user_id):
        """Delete all chat history for user."""
        if not user_id:
            return False
        try:
            db = get_db_client()
            if not db:
                return False
            db.table('chat_history').delete().eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logging.error(f"Error clearing chat history: {e}")
            return False


chatbot_service = MedicalChatbotService()
medical_chatbot = chatbot_service.generate_response

"""
MedScript Blueprints Package
"""

from .main import main_bp
from .auth import auth_bp
from .chat import chat_bp
from .prescription import prescription_bp
from .consultant import consultant_bp
from .doctor import doctor_bp
from .medicine import medicine_bp

__all__ = [
    "main_bp",
    "auth_bp",
    "chat_bp",
    "prescription_bp",
    "consultant_bp",
    "doctor_bp",
    "medicine_bp"
]

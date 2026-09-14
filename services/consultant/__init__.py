"""
MedScript AI Consultant & Disease Prediction Package
"""

from .predictor import (
    consultant_service,
    DiseasePredictorService,
    symptoms_dict,
    diseases_list
)

__all__ = [
    "consultant_service",
    "DiseasePredictorService",
    "symptoms_dict",
    "diseases_list"
]

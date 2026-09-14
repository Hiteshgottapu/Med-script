"""
MedScript Clinical & E-Commerce Validation Engine
Identifies Schedule H / Rx prescription requirements, sanitizes medical records, and validates file uploads.
"""
import re
from typing import Dict, Any, Optional

# Keywords that indicate a prescription-only medicine (Schedule H / Schedule H1 / Schedule X / Rx)
SCHEDULE_H_KEYWORDS = [
    # Antibiotics & Antifungals & Antivirals
    "amoxicillin", "clavulanate", "azithromycin", "ciprofloxacin", "cefixime", "cefpodoxime",
    "ceftriaxone", "cefuroxime", "cefotaxime", "cefdinir", "meropenem", "piperacillin", "tazobactam",
    "doxycycline", "levofloxacin", "ofloxacin", "metronidazole", "fluconazole", "itraconazole",
    "acyclovir", "oseltamivir", "nitrofurantoin", "clarithromycin", "erythromycin", "gentamicin",
    # Antihypertensives & Cardiac
    "telmisartan", "amlodipine", "losartan", "ramipril", "atenolol", "metoprolol", "bisoprolol",
    "enalapril", "olmesartan", "atorvastatin", "rosuvastatin", "clopidogrel", "aspirin 75", "warfarin",
    # Antidiabetics
    "metformin", "glimepiride", "gliclazide", "vildagliptin", "sitagliptin", "dapagliflozin",
    "empagliflozin", "insulin",
    # Psychotropics & Sedatives (Schedule H / X)
    "alprazolam", "clonazepam", "lorazepam", "diazepam", "escitalopram", "sertraline", "fluoxetine",
    "duloxetine", "paroxetine", "amitriptyline", "gabapentin", "pregabalin", "zolpidem",
    # Steroids & Immunosuppressants
    "prednisolone", "dexamethasone", "methylprednisolone", "budesonide", "betamethasone", "hydrocortisone",
    # Prescription Analgesics & Heavy NSAIDs
    "tramadol", "ketorolac", "tapentadol", "nimesulide", "codeine",
    # Respiratory (Inhaled Steroids/LABA)
    "formoterol", "salmeterol", "tiotropium",
    # Gastrointestinal (PPIs usually high strength or combinational)
    "pantoprazole", "rabeprazole", "esomeprazole"
]

def is_prescription_required(
    name: str,
    composition: Optional[str] = None,
    dosage_form: Optional[str] = None,
    source_flag: Optional[bool] = None
) -> bool:
    """
    Clinical assessment of whether a medicine requires a prescription.
    If the source explicitly flags it as Rx, respects that flag.
    Otherwise checks active ingredients and formulation against Schedule H classifications.
    """
    if source_flag is True:
        return True

    text = f"{name or ''} {composition or ''} {dosage_form or ''}".lower()

    # Injections almost universally require prescription / clinical administration
    if (dosage_form and dosage_form.lower() in ["injection", "inj", "infusion", "iv"]) or "injection" in text or "infusion" in text:
        return True

    # Match against Schedule H list
    for kw in SCHEDULE_H_KEYWORDS:
        if kw in text:
            return True

    return False

def validate_product_data(raw: Dict[str, Any]) -> bool:
    """Validates that a scraped/API product record meets minimum quality criteria."""
    name = (raw.get("name") or "").strip()
    if len(name) < 2:
        return False

    price = raw.get("price")
    if price is not None:
        try:
            val = float(price)
            if val < 0 or val > 500000:
                return False
        except (ValueError, TypeError):
            return False

    return True

ALLOWED_PRESCRIPTION_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "webp"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def validate_prescription_file(filename: str, file_size: int) -> Dict[str, Any]:
    """Validates uploaded prescription documents."""
    if not filename:
        return {"valid": False, "error": "No filename provided."}

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_PRESCRIPTION_EXTENSIONS:
        return {"valid": False, "error": f"Invalid file format '.{ext}'. Allowed: PNG, JPG, JPEG, PDF, WEBP."}

    if file_size > MAX_FILE_SIZE_BYTES:
        return {"valid": False, "error": "File size exceeds maximum limit of 10 MB."}

    return {"valid": True, "extension": ext}

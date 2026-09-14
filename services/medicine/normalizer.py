"""
MedScript Medicine Normalizer
Sanitizes raw scraped/API data into consistent, high-quality NormalizedMedicine objects.
"""
import re
import html
from typing import Dict, Any, Optional
import uuid
from .validators import is_prescription_required, validate_product_data

DOSAGE_FORM_MAP = {
    "tab": "Tablet",
    "tabs": "Tablet",
    "tablet": "Tablet",
    "tablets": "Tablet",
    "cap": "Capsule",
    "caps": "Capsule",
    "capsule": "Capsule",
    "capsules": "Capsule",
    "syp": "Syrup",
    "syrup": "Syrup",
    "susp": "Suspension",
    "suspension": "Suspension",
    "soln": "Solution",
    "solution": "Solution",
    "inj": "Injection",
    "injection": "Injection",
    "drop": "Drops",
    "drops": "Drops",
    "oint": "Ointment",
    "ointment": "Ointment",
    "gel": "Gel",
    "crm": "Cream",
    "cream": "Cream",
    "lotion": "Lotion",
    "inhaler": "Inhaler",
    "rotacap": "Rotacaps",
    "powder": "Powder",
    "spray": "Spray"
}

AVAILABILITY_MAP = {
    "available": "In Stock",
    "in stock": "In Stock",
    "instock": "In Stock",
    "true": "In Stock",
    "1": "In Stock",
    "out of stock": "Out of Stock",
    "outofstock": "Out of Stock",
    "false": "Out of Stock",
    "0": "Out of Stock",
    "limited": "Limited",
    "limited stock": "Limited",
    "few left": "Limited",
    "unknown": "Unknown"
}

def sanitize_text(text: Optional[str]) -> Optional[str]:
    """Strip HTML, unescape entities, collapse multi-whitespace, and clean text."""
    if not text:
        return None
    cleaned = re.sub(r"<[^>]*>", " ", str(text))
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else None

def normalize_strength(raw_strength: Optional[str], full_name: Optional[str] = None) -> Optional[str]:
    candidate = raw_strength or ""
    if not candidate and full_name:
        match = re.search(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|%|gm)(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)?)?)", full_name, re.IGNORECASE)
        if match:
            candidate = match.group(1)

    if not candidate:
        return None

    candidate = candidate.strip()
    candidate = re.sub(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)", lambda m: f"{m.group(1)} {m.group(2).lower()}", candidate)
    candidate = re.sub(r"\s*/\s*", " / ", candidate)
    return candidate.strip()

def normalize_dosage_form(raw_form: Optional[str], full_name: Optional[str] = None) -> Optional[str]:
    text = (raw_form or "").lower().strip()
    if not text and full_name:
        text = full_name.lower().strip()

    for key, mapped in DOSAGE_FORM_MAP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", text):
            return mapped

    if raw_form:
        clean = sanitize_text(raw_form)
        return clean.title() if clean else None
    return None

def normalize_price(raw_price: Any) -> Optional[float]:
    if raw_price is None or raw_price == "":
        return None
    try:
        if isinstance(raw_price, (int, float)):
            val = float(raw_price)
        else:
            clean = re.sub(r"[^\d.]", "", str(raw_price))
            val = float(clean) if clean else None
        
        if val is not None and val >= 0:
            return round(val, 2)
        return None
    except (ValueError, TypeError):
        return None

def normalize_availability(raw_avail: Any) -> str:
    if raw_avail is None:
        return "Unknown"
    norm = str(raw_avail).strip().lower()
    return AVAILABILITY_MAP.get(norm, "In Stock" if "stock" in norm and "out" not in norm else "Unknown")

def sanitize_url(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None
    clean = raw_url.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    return None

def normalize_medicine_record(raw: Dict[str, Any], source_default: str = "Unknown") -> Optional[Dict[str, Any]]:
    """
    Validates and normalizes raw dictionary into standardized schema.
    Returns None if record fails quality checks.
    """
    if not validate_product_data(raw):
        return None

    name = sanitize_text(raw.get("name"))
    if not name or len(name) < 2:
        return None

    brand = sanitize_text(raw.get("brand_name")) or name
    generic = sanitize_text(raw.get("generic_name"))
    full_str = f"{name} {brand or ''} {generic or ''}"

    strength = normalize_strength(raw.get("strength"), full_str)
    form = normalize_dosage_form(raw.get("dosage_form") or raw.get("form"), full_str)
    composition = sanitize_text(raw.get("composition"))
    manufacturer = sanitize_text(raw.get("manufacturer"))
    pack_size = sanitize_text(raw.get("pack_size") or raw.get("packaging"))

    price = normalize_price(raw.get("price"))
    mrp = normalize_price(raw.get("mrp"))
    discount = normalize_price(raw.get("discount") or raw.get("discount_percent"))
    
    if mrp and price and mrp > price and not discount:
        discount = round(((mrp - price) / mrp) * 100, 1)

    currency = sanitize_text(raw.get("currency")) or "INR"
    availability = normalize_availability(raw.get("availability"))
    source = sanitize_text(raw.get("source")) or source_default
    source_product_id = sanitize_text(raw.get("source_product_id"))
    source_url = sanitize_url(raw.get("source_url") or raw.get("url"))
    image_url = sanitize_url(raw.get("image_url"))

    # Determine prescription requirement
    source_rx_flag = raw.get("prescription_required")
    rx_req = is_prescription_required(
        name=name,
        composition=composition,
        dosage_form=form,
        source_flag=source_rx_flag
    )

    product_type = sanitize_text(raw.get("product_type")) or "ALLOPATHY"

    med_id = raw.get("id") or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source}_{name}_{strength}_{form}"))

    return {
        "id": str(med_id),
        "source": source,
        "source_product_id": source_product_id or str(med_id),
        "source_url": source_url,
        "name": name,
        "brand_name": brand,
        "generic_name": generic,
        "strength": strength,
        "dosage_form": form,
        "composition": composition,
        "manufacturer": manufacturer,
        "pack_size": pack_size,
        "price": price,
        "mrp": mrp,
        "discount": discount,
        "currency": currency,
        "availability": availability,
        "stock_status": availability,
        "image_url": image_url,
        "prescription_required": rx_req,
        "product_type": product_type
    }

"""
MedScript Prescription Generator & Clinical Structured Formatter
"""

import re
import json
import logging
from datetime import datetime

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


def build_clean_transcript(p):
    """Formats structured prescription JSON into a professional medical document."""
    if not isinstance(p, dict):
        return str(p)

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
        lines.append(f"Reg No: {doc.get('reg_no')}")
    if doc.get("phone"):
        lines.append(f"Phone: {doc.get('phone')}")

    lines.append("-" * 40)

    pat = p.get("patient", {}) if isinstance(p.get("patient"), dict) else {}
    pat_line = f"Patient: {pat.get('name') or 'N/A'}"
    meta = []
    if pat.get("age"):
        meta.append(f"Age: {pat.get('age')}")
    if pat.get("gender"):
        meta.append(f"Gender: {pat.get('gender')}")
    if pat.get("date"):
        meta.append(f"Date: {pat.get('date')}")
    if meta:
        pat_line += " | " + " | ".join(meta)
    lines.append(pat_line)

    if pat.get("allergies"):
        lines.append(f"Allergies: {pat.get('allergies')}")

    lines.append("-" * 40)

    clin = p.get("clinical", {}) if isinstance(p.get("clinical"), dict) else {}
    if clin.get("diagnosis"):
        lines.append(f"Diagnosis: {clin.get('diagnosis')}")
    if clin.get("symptoms"):
        lines.append(f"Symptoms: {clin.get('symptoms')}")
    if clin.get("notes"):
        lines.append(f"Notes: {clin.get('notes')}")

    lines.append("-" * 40)
    lines.append("Rx (MEDICATIONS):")

    meds = p.get("medicines", [])
    if isinstance(meds, list) and meds:
        for i, m in enumerate(meds, 1):
            if isinstance(m, dict):
                m_name = m.get("name") or "Medicine"
                m_str = m.get("strength") or ""
                m_form = m.get("form") or "Tablet"
                head = f"{i}. {m_name}"
                if m_str:
                    head += f" {m_str}"
                head += f" ({m_form})"
                lines.append(head)

                parts = []
                if m.get("dose"):
                    parts.append(f"Dose: {m.get('dose')}")
                if m.get("frequency"):
                    parts.append(f"Freq: {m.get('frequency')}")
                if m.get("duration"):
                    parts.append(f"Dur: {m.get('duration')}")
                if m.get("timing"):
                    parts.append(f"Timing: {m.get('timing')}")
                if parts:
                    lines.append("   " + " | ".join(parts))
                if m.get("instructions"):
                    lines.append(f"   Instructions: {m.get('instructions')}")
            else:
                lines.append(f"{i}. {str(m)}")
    else:
        lines.append("No medications listed.")

    lines.append("-" * 40)

    instr = p.get("instructions", {}) if isinstance(p.get("instructions"), dict) else {}
    if instr.get("general"):
        lines.append(f"Advice: {instr.get('general')}")
    if instr.get("diet"):
        lines.append(f"Diet: {instr.get('diet')}")
    if instr.get("follow_up"):
        lines.append(f"Follow Up: {instr.get('follow_up')}")

    lines.append("-" * 40)
    lines.append("Doctor Signature: _______________________")

    return "\n".join(lines)


def parse_prescription_response(raw_text):
    """Extracts clean JSON from model output with regex fallback."""
    if not raw_text:
        return {}
    raw = raw_text.strip()

    # Try exact JSON first
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Try markdown json fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    # Try finding outer braces
    brace_match = re.search(r"(\{[\s\S]*\})", raw)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except Exception:
            pass

    return {"raw_transcript": raw}

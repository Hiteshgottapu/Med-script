"""
MedScript Prescription Scanner, Generator & Export Blueprint
"""

import os
import random
import logging
from datetime import datetime
from flask import Blueprint, request, render_template, session, jsonify, send_file, url_for
from services.prescription import (
    COMMON_MEDICATIONS_DB,
    build_clean_transcript,
    extract_text_from_image,
    generate_prescription_pdf
)

prescription_bp = Blueprint('prescription', __name__)


@prescription_bp.route("/api/medicine-autocomplete", methods=["GET"])
def medicine_autocomplete():
    query = request.args.get("query", "").strip().lower()
    if not query:
        return jsonify(COMMON_MEDICATIONS_DB[:10])

    matches = []
    for med in COMMON_MEDICATIONS_DB:
        if query in med["name"].lower():
            matches.append(med)
        if len(matches) >= 12:
            break

    return jsonify(matches)


@prescription_bp.route("/api/generate-prescription", methods=["POST"])
def api_generate_prescription():
    try:
        data = request.get_json(force=True) or {}
        patient = data.get("patient", {})
        clinical = data.get("clinical", {})
        medicines = data.get("medicines", [])
        instructions = data.get("instructions", {})

        if not patient.get("name"):
            return jsonify({"success": False, "error": "Patient name is required."}), 400
        if not medicines:
            return jsonify({"success": False, "error": "At least one medication is required."}), 400

        rx_id = f"RX-{datetime.now().strftime('%y%m%d')}-{random.randint(1000, 9999)}"
        created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
        date_str = datetime.now().strftime("%d %b %Y")

        lines = [
            "MEDSCRIPT CLINICAL WORKSPACE",
            f"Prescription ID: {rx_id} | Date: {date_str}",
            "-" * 40,
            f"Patient: {patient.get('name')} | Age: {patient.get('age', 'N/A')} | Gender: {patient.get('gender', 'N/A')}"
        ]
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

        if "prescription_history" not in session:
            session["prescription_history"] = []

        session["prescription_history"].insert(0, prescription_obj)
        session["prescription_history"] = session["prescription_history"][:10]
        session.modified = True

        return jsonify({
            "success": True,
            "prescription": prescription_obj,
            "formatted_text": formatted_text,
            "pdf_url": url_for("prescription.download_pdf", text=formatted_text)
        })

    except Exception as e:
        logging.error(f"Prescription generation error: {e}")
        return jsonify({"success": False, "error": f"Failed to generate prescription: {str(e)}"}), 500


@prescription_bp.route("/medscript", methods=["GET", "POST"])
def medscript():
    recent_prescriptions = session.get("prescription_history", [])
    if request.method == "POST":
        file = request.files.get("image")
        if file and file.filename != "":
            ocr_result = extract_text_from_image(file)
            extracted_text = ocr_result.get("text") if isinstance(ocr_result, dict) else str(ocr_result)
            parsed_data = ocr_result.get("parsed") if isinstance(ocr_result, dict) else None
            return render_template(
                "medscript.html",
                text=extracted_text,
                parsed_data=parsed_data,
                recent_prescriptions=recent_prescriptions
            )
    return render_template("medscript.html", recent_prescriptions=recent_prescriptions)


@prescription_bp.route('/download_pdf')
def download_pdf():
    text = request.args.get('text', '')
    buffer = generate_prescription_pdf(text)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="medscript_prescription.pdf",
        mimetype="application/pdf"
    )

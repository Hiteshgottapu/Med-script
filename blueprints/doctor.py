"""
MedScript Doctor Consultation & Emergency Blueprint
"""

import logging
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from services.notifications import send_email, notification_service

doctor_bp = Blueprint('doctor', __name__)

CLINICAL_DOCTORS = [
    {
        "id": "doc_1",
        "name": "Dr. Suresh Reddy, M.D.",
        "specialization": "Internal Medicine & General Physician",
        "hospital": "Care Hospitals, Banjara Hills",
        "email": "dr.suresh.reddy@carehospitals.com",
        "rating": 4.9,
        "experience": "16+ years",
        "keywords": ["fever", "cough", "cold", "infection", "headache", "general", "body ache", "fatigue", "weakness"]
    },
    {
        "id": "doc_2",
        "name": "Dr. Priya Sharma, M.D., DNB",
        "specialization": "Dermatologist & Cosmetologist",
        "hospital": "Fortis Healthcare",
        "email": "dr.priya.sharma@fortis.com",
        "rating": 4.8,
        "experience": "12+ years",
        "keywords": ["skin", "rash", "itching", "acne", "hair", "allergy", "dermatologist", "spots", "dermatology"]
    },
    {
        "id": "doc_3",
        "name": "Dr. Ramesh Kumar, M.D., DM",
        "specialization": "Cardiologist",
        "hospital": "Apollo Hospitals, Heart Institute",
        "email": "dr.ramesh.kumar@apollohospitals.com",
        "rating": 4.9,
        "experience": "20+ years",
        "keywords": ["heart", "chest pain", "blood pressure", "hypertension", "palpitations", "cardio", "cardiologist"]
    },
    {
        "id": "doc_4",
        "name": "Dr. Arvind Swaminathan, DM",
        "specialization": "Neurologist",
        "hospital": "Manipal Hospitals",
        "email": "dr.arvind.s@manipal.com",
        "rating": 4.9,
        "experience": "18+ years",
        "keywords": ["headache", "migraine", "dizziness", "nerve", "seizure", "numbness", "neurologist", "neurology"]
    },
    {
        "id": "doc_5",
        "name": "Dr. Rajesh Patel, M.S., M.Ch",
        "specialization": "Orthopedic Surgeon",
        "hospital": "Max Super Speciality Hospital",
        "email": "dr.rajesh.patel@maxhealthcare.com",
        "rating": 4.7,
        "experience": "15+ years",
        "keywords": ["joint", "bone", "knee", "back pain", "fracture", "arthritis", "orthopedic", "orthopedist"]
    },
    {
        "id": "doc_6",
        "name": "Dr. Ananya Mukherjee, M.D.",
        "specialization": "Pulmonologist & Chest Specialist",
        "hospital": "Apollo Hospitals",
        "email": "dr.ananya.m@apollohospitals.com",
        "rating": 4.8,
        "experience": "14+ years",
        "keywords": ["cough", "breath", "breathing", "asthma", "chest", "lungs", "pulmonologist", "wheezing"]
    }
]


@doctor_bp.route("/doctor_consultation", methods=["GET", "POST"])
def doctor_consultation():
    name = request.form.get("name", "")
    age = request.form.get("age", "")
    email = request.form.get("email", "")
    symptoms = request.form.get("symptoms", "").strip()

    # Also support query parameter for category quick-filtering
    category = request.args.get("category", "").strip().lower()
    search_term = (symptoms or category).lower()

    if search_term:
        matched = []
        for doc in CLINICAL_DOCTORS:
            blob = f"{doc['name'].lower()} {doc['specialization'].lower()} {' '.join(doc['keywords'])}"
            if any(k in blob for k in search_term.split()):
                matched.append(doc)
        doctors = matched if matched else CLINICAL_DOCTORS
    else:
        doctors = CLINICAL_DOCTORS if request.method == "POST" else []

    return render_template(
        "doctor_consultation.html",
        doctors=doctors,
        name=name,
        age=age,
        email=email,
        symptoms=symptoms
    )


@doctor_bp.route("/schedule_appointment", methods=["POST"])
def schedule_appointment():
    patient_name = request.form.get("patient_name")
    doctor_name = request.form.get("doctor_name")
    doctor_email = request.form.get("doctor_email")
    hospital_email = request.form.get("hospital_email")
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    additional_details = request.form.get("reason") or request.form.get("additional_details")

    subject = f"Appointment Request with {doctor_name}"
    body = (
        f"Dear {doctor_name},\n\n"
        f"You have a new appointment request from {patient_name}.\n\n"
        f"Appointment Details:\n"
        f"- Date: {appointment_date}\n"
        f"- Time: {appointment_time}\n"
        f"- Details: {additional_details}\n\n"
        f"Regards,\nMedScript Team"
    )

    if doctor_email: send_email(doctor_email, subject, body)
    if hospital_email: send_email(hospital_email, subject, body)

    flash(f"Appointment request for {doctor_name} on {appointment_date} sent successfully!", "success")
    return redirect(url_for("doctor.doctor_consultation"))


@doctor_bp.route("/send_message", methods=["POST"])
def send_message():
    name = request.form.get("name")
    message = request.form.get("message")
    email = request.form.get("email")

    subject = f"Clinical Inquiry from {name}"
    body = f"From: {name} ({email})\n\nMessage:\n{message}"
    send_email("hiteshgottapu@gmail.com", subject, body)

    return jsonify({"success": True, "message": "Message sent successfully!"})


@doctor_bp.route("/emergency", methods=["GET"])
def emergency():
    return render_template("emergency.html")


@doctor_bp.route("/api/emergency-alert", methods=["POST"])
def api_emergency_alert():
    data = request.get_json(silent=True) or {}
    user_name = data.get("name", "MedScript Patient")
    user_phone = data.get("phone", "Emergency Contact")
    location = data.get("location", "Current GPS Position")
    alert_type = data.get("alert_type", "URGENT SOS")

    success = notification_service.trigger_emergency_alert(user_name, user_phone, location, alert_type)
    session["emergency_alerts_count"] = session.get("emergency_alerts_count", 0) + 1
    session.modified = True
    return jsonify({
        "success": True,
        "dispatched": success,
        "message": "Emergency broadcast alert dispatched to on-call responders and contacts."
    })

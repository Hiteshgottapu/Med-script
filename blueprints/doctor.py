"""
MedScript Doctor Consultation & Emergency Blueprint
"""

import logging
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from services.notifications import send_email, notification_service

doctor_bp = Blueprint('doctor', __name__)

CLINICAL_DOCTORS = [
    # --- PULMONOLOGY & CHEST MEDICINE ---
    {
        "id": "doc_pulm_1",
        "name": "Dr. Ananya Mukherjee, M.D.",
        "specialization": "Pulmonologist & Chest Specialist",
        "hospital": "Apollo Hospitals, Jubilee Hills",
        "email": "dr.ananya.m@apollohospitals.com",
        "rating": 4.8,
        "experience": "14+ years",
        "fee": "₹800",
        "available_time": "Today, 4:30 PM",
        "consult_type": "Video & In-Clinic",
        "keywords": ["cough", "breath", "breathing", "asthma", "chest", "lungs", "pulmonologist", "pulmonology", "wheezing", "shortness of breath", "bronchitis", "pneumonia", "respiratory"]
    },
    {
        "id": "doc_pulm_2",
        "name": "Dr. Vikramaditya Rao, M.D., DM",
        "specialization": "Senior Pulmonologist & Interventional Specialist",
        "hospital": "Yashoda Hospitals, Secunderabad",
        "email": "dr.vikram.rao@yashodahospitals.com",
        "rating": 4.9,
        "experience": "18+ years",
        "fee": "₹1,000",
        "available_time": "Today, 6:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["cough", "breath", "breathing", "asthma", "chest", "lungs", "pulmonologist", "pulmonology", "copd", "interventional pulmonology", "allergy", "chest pain"]
    },
    {
        "id": "doc_pulm_3",
        "name": "Dr. Rituja Deshmukh, DNB, FCCP",
        "specialization": "Chest Physician & Sleep Apnea Specialist",
        "hospital": "Care Hospitals, Banjara Hills",
        "email": "dr.rituja.d@carehospitals.com",
        "rating": 4.7,
        "experience": "11+ years",
        "fee": "₹700",
        "available_time": "Tomorrow, 10:30 AM",
        "consult_type": "Video Consult",
        "keywords": ["cough", "breath", "breathing", "asthma", "chest", "lungs", "pulmonologist", "pulmonology", "snoring", "sleep apnea", "tb", "tuberculosis", "cold"]
    },
    {
        "id": "doc_pulm_4",
        "name": "Dr. Arvind Mehta, M.D., DNB",
        "specialization": "Pulmonologist & Critical Care",
        "hospital": "Fortis Healthcare, Bannerghatta",
        "email": "dr.arvind.mehta@fortis.com",
        "rating": 4.9,
        "experience": "16+ years",
        "fee": "₹900",
        "available_time": "Tomorrow, 2:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["cough", "breath", "breathing", "asthma", "chest", "lungs", "pulmonologist", "pulmonology", "lung infection", "oxygen", "chronic cough"]
    },

    # --- CARDIOLOGY ---
    {
        "id": "doc_card_1",
        "name": "Dr. Ramesh Kumar, M.D., DM",
        "specialization": "Senior Interventional Cardiologist",
        "hospital": "Apollo Hospitals, Heart Institute",
        "email": "dr.ramesh.kumar@apollohospitals.com",
        "rating": 4.9,
        "experience": "20+ years",
        "fee": "₹1,200",
        "available_time": "Today, 5:15 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["heart", "chest pain", "blood pressure", "hypertension", "palpitations", "cardio", "cardiologist", "cardiology", "arrhythmia", "cholesterol", "angina"]
    },
    {
        "id": "doc_card_2",
        "name": "Dr. Sanjay Kapoor, M.D., DM, FACC",
        "specialization": "Cardiologist & Electrophysiologist",
        "hospital": "Fortis Escorts Heart Institute",
        "email": "dr.sanjay.kapoor@fortis.com",
        "rating": 4.8,
        "experience": "17+ years",
        "fee": "₹1,100",
        "available_time": "Tomorrow, 11:00 AM",
        "consult_type": "Video Consult",
        "keywords": ["heart", "chest pain", "blood pressure", "hypertension", "palpitations", "cardio", "cardiologist", "cardiology", "heart failure", "ecg", "cardiac"]
    },
    {
        "id": "doc_card_3",
        "name": "Dr. Meenakshi Sundaram, M.D., DM",
        "specialization": "Clinical Cardiologist & Preventive Care",
        "hospital": "Max Super Speciality Hospital",
        "email": "dr.meenakshi.s@maxhealthcare.com",
        "rating": 4.9,
        "experience": "15+ years",
        "fee": "₹950",
        "available_time": "Today, 7:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["heart", "chest pain", "blood pressure", "hypertension", "palpitations", "cardio", "cardiologist", "cardiology", "lipid", "cardiac risk"]
    },

    # --- DERMATOLOGY ---
    {
        "id": "doc_derm_1",
        "name": "Dr. Priya Sharma, M.D., DNB",
        "specialization": "Dermatologist & Cosmetologist",
        "hospital": "Fortis Healthcare",
        "email": "dr.priya.sharma@fortis.com",
        "rating": 4.8,
        "experience": "12+ years",
        "fee": "₹750",
        "available_time": "Today, 4:00 PM",
        "consult_type": "Video & In-Clinic",
        "keywords": ["skin", "rash", "itching", "acne", "hair", "allergy", "dermatologist", "dermatology", "spots", "eczema", "psoriasis", "fungal", "skin peeling"]
    },
    {
        "id": "doc_derm_2",
        "name": "Dr. Rohan Varma, M.D.",
        "specialization": "Consultant Dermatologist & Trichologist",
        "hospital": "Apollo Clinics, Kondapur",
        "email": "dr.rohan.varma@apollohospitals.com",
        "rating": 4.9,
        "experience": "15+ years",
        "fee": "₹850",
        "available_time": "Tomorrow, 10:00 AM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["skin", "rash", "itching", "acne", "hair", "allergy", "dermatologist", "dermatology", "hair loss", "scalp", "pigmentation", "skin infection"]
    },
    {
        "id": "doc_derm_3",
        "name": "Dr. Shalini Kulkarni, M.D., DVD",
        "specialization": "Pediatric & Aesthetic Dermatologist",
        "hospital": "Care Hospitals, Hitec City",
        "email": "dr.shalini.k@carehospitals.com",
        "rating": 4.7,
        "experience": "9+ years",
        "fee": "₹650",
        "available_time": "Today, 6:30 PM",
        "consult_type": "Video Consult",
        "keywords": ["skin", "rash", "itching", "acne", "hair", "allergy", "dermatologist", "dermatology", "mole", "warts", "dermatitis"]
    },

    # --- NEUROLOGY ---
    {
        "id": "doc_neuro_1",
        "name": "Dr. Arvind Swaminathan, DM",
        "specialization": "Senior Consultant Neurologist",
        "hospital": "Manipal Hospitals, Whitefield",
        "email": "dr.arvind.s@manipal.com",
        "rating": 4.9,
        "experience": "18+ years",
        "fee": "₹1,200",
        "available_time": "Today, 5:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["headache", "migraine", "dizziness", "nerve", "seizure", "numbness", "neurologist", "neurology", "brain", "vertigo", "stroke", "tremors", "paralysis"]
    },
    {
        "id": "doc_neuro_2",
        "name": "Dr. Neha Singhal, M.D., DM",
        "specialization": "Neurologist & Movement Disorder Specialist",
        "hospital": "Apollo Hospitals, Central",
        "email": "dr.neha.singhal@apollohospitals.com",
        "rating": 4.8,
        "experience": "13+ years",
        "fee": "₹900",
        "available_time": "Tomorrow, 11:30 AM",
        "consult_type": "Video Consult",
        "keywords": ["headache", "migraine", "dizziness", "nerve", "seizure", "numbness", "neurologist", "neurology", "epilepsy", "parkinson", "memory loss"]
    },
    {
        "id": "doc_neuro_3",
        "name": "Dr. V. S. Ramachandra, M.D., DM",
        "specialization": "Neuro Physician & Stroke Specialist",
        "hospital": "Yashoda Hospitals, Somajiguda",
        "email": "dr.vs.ramachandra@yashodahospitals.com",
        "rating": 4.9,
        "experience": "22+ years",
        "fee": "₹1,300",
        "available_time": "Today, 7:30 PM",
        "consult_type": "In-Clinic Only",
        "keywords": ["headache", "migraine", "dizziness", "nerve", "seizure", "numbness", "neurologist", "neurology", "neuralgia", "spinal pain", "balance"]
    },

    # --- ORTHOPEDICS ---
    {
        "id": "doc_ortho_1",
        "name": "Dr. Rajesh Patel, M.S., M.Ch",
        "specialization": "Orthopedic & Joint Replacement Surgeon",
        "hospital": "Max Super Speciality Hospital",
        "email": "dr.rajesh.patel@maxhealthcare.com",
        "rating": 4.8,
        "experience": "15+ years",
        "fee": "₹900",
        "available_time": "Today, 4:45 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["joint", "bone", "knee", "back pain", "fracture", "arthritis", "orthopedic", "orthopedist", "orthopaedics", "shoulder", "ligament", "hip pain"]
    },
    {
        "id": "doc_ortho_2",
        "name": "Dr. Harish Chandra, M.S. Ortho, Fellowship (UK)",
        "specialization": "Spine & Sports Injury Specialist",
        "hospital": "Apollo Hospitals, Jubilee Hills",
        "email": "dr.harish.chandra@apollohospitals.com",
        "rating": 4.9,
        "experience": "19+ years",
        "fee": "₹1,100",
        "available_time": "Tomorrow, 12:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["joint", "bone", "knee", "back pain", "fracture", "arthritis", "orthopedic", "orthopedist", "spine", "slip disc", "sciatica", "neck pain", "sports injury"]
    },
    {
        "id": "doc_ortho_3",
        "name": "Dr. Sneha Joshi, DNB Ortho",
        "specialization": "Orthopedic Surgeon & Arthroscopy",
        "hospital": "Care Hospitals, Banjara Hills",
        "email": "dr.sneha.joshi@carehospitals.com",
        "rating": 4.7,
        "experience": "10+ years",
        "fee": "₹700",
        "available_time": "Today, 6:15 PM",
        "consult_type": "Video Consult",
        "keywords": ["joint", "bone", "knee", "back pain", "fracture", "arthritis", "orthopedic", "orthopedist", "muscle tear", "tendon", "sprain"]
    },

    # --- INTERNAL MEDICINE & GENERAL PHYSICIAN ---
    {
        "id": "doc_gen_1",
        "name": "Dr. Suresh Reddy, M.D.",
        "specialization": "Internal Medicine & General Physician",
        "hospital": "Care Hospitals, Banjara Hills",
        "email": "dr.suresh.reddy@carehospitals.com",
        "rating": 4.9,
        "experience": "16+ years",
        "fee": "₹600",
        "available_time": "Today, 3:30 PM",
        "consult_type": "Video & In-Clinic",
        "keywords": ["fever", "cough", "cold", "infection", "headache", "general", "body ache", "fatigue", "weakness", "physician", "flu", "viral", "malaise"]
    },
    {
        "id": "doc_gen_2",
        "name": "Dr. Anjali Nair, M.D., PGDGM",
        "specialization": "Consultant Physician & Diabetologist",
        "hospital": "Apollo Clinics, Madhapur",
        "email": "dr.anjali.nair@apollohospitals.com",
        "rating": 4.8,
        "experience": "14+ years",
        "fee": "₹650",
        "available_time": "Today, 5:00 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["fever", "diabetes", "blood sugar", "thyroid", "fatigue", "general", "infection", "hypertension", "metabolic", "weakness"]
    },
    {
        "id": "doc_gen_3",
        "name": "Dr. Mohit Gupta, M.D.",
        "specialization": "General Medicine & Infectious Diseases",
        "hospital": "Fortis Hospital, Cunningham Road",
        "email": "dr.mohit.gupta@fortis.com",
        "rating": 4.8,
        "experience": "12+ years",
        "fee": "₹700",
        "available_time": "Tomorrow, 9:30 AM",
        "consult_type": "Video Consult",
        "keywords": ["fever", "typhoid", "malaria", "dengue", "chills", "infection", "cough", "general", "vomiting", "nausea"]
    },

    # --- GASTROENTEROLOGY ---
    {
        "id": "doc_gastro_1",
        "name": "Dr. Amitava Ghosh, M.D., DM",
        "specialization": "Senior Medical Gastroenterologist & Hepatologist",
        "hospital": "Asian Institute of Gastroenterology (AIG)",
        "email": "dr.amitava.ghosh@aighospitals.com",
        "rating": 4.9,
        "experience": "19+ years",
        "fee": "₹1,000",
        "available_time": "Today, 5:30 PM",
        "consult_type": "In-Clinic & Video",
        "keywords": ["stomach", "acidity", "gastric", "gerd", "liver", "jaundice", "gastroenterologist", "gastroenterology", "abdomen", "diarrhea", "constipation", "ulcer", "vomiting", "indigestion"]
    },
    {
        "id": "doc_gastro_2",
        "name": "Dr. Radhika Iyer, M.D., DM",
        "specialization": "Gastroenterologist & Therapeutic Endoscopist",
        "hospital": "Apollo Hospitals, Heart & Liver Institute",
        "email": "dr.radhika.iyer@apollohospitals.com",
        "rating": 4.8,
        "experience": "13+ years",
        "fee": "₹850",
        "available_time": "Tomorrow, 10:30 AM",
        "consult_type": "Video & In-Clinic",
        "keywords": ["stomach", "acidity", "gastric", "gerd", "liver", "gastroenterologist", "gastroenterology", "ibs", "colon", "bloating", "gas", "abdominal pain"]
    },
    {
        "id": "doc_gastro_3",
        "name": "Dr. Deepak Verma, M.S., M.Ch",
        "specialization": "GI & Hepato-Pancreato-Biliary Surgeon",
        "hospital": "Fortis Healthcare, Bannerghatta",
        "email": "dr.deepak.verma@fortis.com",
        "rating": 4.9,
        "experience": "17+ years",
        "fee": "₹1,100",
        "available_time": "Today, 6:45 PM",
        "consult_type": "In-Clinic Only",
        "keywords": ["stomach", "gastric", "gastroenterologist", "gastroenterology", "gallbladder", "hernia", "appendix", "piles", "fissure", "pancreas"]
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
        search_words = [w.strip() for w in search_term.replace(',', ' ').split() if len(w.strip()) > 1]
        matched = []
        for doc in CLINICAL_DOCTORS:
            blob = f"{doc['name'].lower()} {doc['specialization'].lower()} {doc['hospital'].lower()} {' '.join(doc['keywords'])}"
            # Match if any search token is in the doctor's profile or keywords
            if any(w in blob for w in search_words):
                matched.append(doc)
        doctors = matched if matched else CLINICAL_DOCTORS
    else:
        # Default view: show all available clinical doctors so the user has immediate choices
        doctors = CLINICAL_DOCTORS

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

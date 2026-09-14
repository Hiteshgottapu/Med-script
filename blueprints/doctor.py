"""
MedScript Doctor Consultation & Emergency Blueprint
"""

import logging
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from services.notifications import send_email, notification_service

doctor_bp = Blueprint('doctor', __name__)


@doctor_bp.route("/doctor_consultation", methods=["GET", "POST"])
def doctor_consultation():
    return render_template("doctor_consultation.html")


@doctor_bp.route("/schedule_appointment", methods=["POST"])
def schedule_appointment():
    patient_name = request.form.get("patient_name")
    doctor_name = request.form.get("doctor_name")
    doctor_email = request.form.get("doctor_email")
    hospital_email = request.form.get("hospital_email")
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    additional_details = request.form.get("additional_details")

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

    flash("Appointment request sent successfully!", "success")
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
    return jsonify({
        "success": True,
        "dispatched": success,
        "message": "Emergency broadcast alert dispatched to on-call responders and contacts."
    })

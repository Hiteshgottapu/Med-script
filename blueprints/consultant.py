"""
MedScript AI Consultant & Symptom Checker Blueprint
"""

import logging
from flask import Blueprint, request, render_template, jsonify
from services.consultant import consultant_service

consultant_bp = Blueprint('consultant', __name__)


@consultant_bp.route("/ai_consultant", methods=["GET"])
def ai_consultant():
    return render_template("ai_consultant.html")


@consultant_bp.route("/predict", methods=['POST'])
def predict():
    name = request.form.get('name')
    age = request.form.get('age')
    location = request.form.get('location')
    symptoms = request.form.get('symptoms')

    if symptoms == "Symptoms" or not symptoms:
        message = "Please enter valid symptoms to analyze."
        return render_template('ai_consultant.html', message=message)

    user_symptoms = [s.strip("[]' ") for s in symptoms.split(',') if s.strip()]
    disease_set = set()
    predictions = []

    top_n = 1 if len(user_symptoms) == 1 else 3
    top_diseases = consultant_service.get_top_predicted_values(user_symptoms, top_n=top_n)

    for idx, predicted_disease in top_diseases:
        if predicted_disease not in disease_set:
            disease_set.add(predicted_disease)
            dis_des, pre, med, rec_diet, wrkout = consultant_service.get_disease_details(predicted_disease)
            my_precautions = pre[0] if pre and len(pre) > 0 else []
            predictions.append({
                'predicted_disease': predicted_disease,
                'dis_des': dis_des,
                'my_precautions': my_precautions,
                'medications': med,
                'my_diet': rec_diet,
                'workout': wrkout
            })

    return render_template(
        'ai_consultant.html',
        name=name,
        age=age,
        location=location,
        symptoms=symptoms,
        predictions=predictions
    )


@consultant_bp.route("/api/symptom-check", methods=["POST"])
def api_symptom_check():
    data = request.get_json(silent=True) or {}
    symptoms = data.get("symptoms", "")
    age = data.get("age")
    sex = data.get("sex", "male")

    if not symptoms:
        return jsonify({"success": False, "error": "Symptoms are required"}), 400

    symptoms_list = [s.strip("[]' ") for s in symptoms.split(',') if s.strip()]
    top_diseases = consultant_service.get_top_predicted_values(symptoms_list, top_n=3)

    results = []
    for idx, disease in top_diseases:
        desc, pre, med, diet, workout = consultant_service.get_disease_details(disease)
        results.append({
            "name": disease,
            "description": desc,
            "precautions": pre[0] if pre else [],
            "medications": med,
            "diet": diet,
            "workout": workout
        })

    return jsonify({"success": True, "conditions": results})

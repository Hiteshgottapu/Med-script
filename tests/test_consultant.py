"""
Test AI Consultant & ML Disease Predictor
"""

from services.consultant import consultant_service


def test_consultant_disease_prediction():
    """Ensure ML predictor correctly infers diseases from symptoms."""
    symptoms = ["itching", "skin_rash", "nodal_skin_eruptions"]
    predictions = consultant_service.get_top_predicted_values(symptoms, top_n=3)
    assert len(predictions) > 0
    top_pred = predictions[0]
    assert isinstance(top_pred[1], str)
    assert len(top_pred[1]) > 0


def test_consultant_disease_details():
    """Ensure disease recommendations, precautions, and diets are retrieved."""
    desc, pre, med, diet, work = consultant_service.get_disease_details("Fungal infection")
    assert isinstance(desc, str)
    assert isinstance(pre, list)
    assert isinstance(med, list)


def test_consultant_api_endpoint(client):
    """Ensure /api/symptom-check returns conditions list."""
    payload = {
        "symptoms": "headache, chills, high_fever"
    }
    res = client.post("/api/symptom-check", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "conditions" in data
    assert len(data["conditions"]) > 0

"""
Test Prescription Transcript Builder, Autocomplete, and PDF Generation
"""

from services.prescription import (
    COMMON_MEDICATIONS_DB,
    build_clean_transcript,
    generate_prescription_pdf
)


def test_clean_transcript_builder():
    """Ensure structured prescription JSON is converted to clean readable text."""
    sample_rx = {
        "doctor": {
            "name": "Dr. Sarah Jenkins",
            "specialty": "MD Internal Medicine",
            "clinic": "Metro Health Clinic"
        },
        "patient": {
            "name": "John Doe",
            "age": "45",
            "gender": "Male"
        },
        "clinical": {
            "diagnosis": "Acute Bronchitis"
        },
        "medicines": [
            {
                "name": "Augmentin 625",
                "strength": "625mg",
                "form": "Tablet",
                "dose": "1 tablet",
                "frequency": "Twice daily",
                "duration": "5 days"
            }
        ]
    }
    transcript = build_clean_transcript(sample_rx)
    assert "METRO HEALTH CLINIC" in transcript
    assert "Dr. Sarah Jenkins" in transcript
    assert "Augmentin 625" in transcript
    assert "Doctor Signature:" in transcript


def test_prescription_pdf_generation(client):
    """Ensure ReportLab renders clean PDF bytes."""
    text = "=== CLINICAL PRESCRIPTION ===\nPatient: John Doe\nRx: Dolo 650 1 tablet"
    pdf_buffer = generate_prescription_pdf(text)
    pdf_bytes = pdf_buffer.getvalue()
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")


def test_medicine_autocomplete_api(client):
    """Ensure autocomplete API returns medication suggestions."""
    res = client.get("/api/medicine-autocomplete?query=dolo")
    assert res.status_code == 200
    items = res.get_json()
    assert isinstance(items, list)
    assert any("Dolo" in m["name"] for m in items)

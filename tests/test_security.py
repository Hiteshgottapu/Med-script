"""
Test Application Security, Auth Protections, and File Validation
"""

import io
from services.medicine.validators import validate_prescription_file


def test_prescription_file_validation_security():
    """Ensure malicious files and oversized uploads are rejected."""
    # Disallow executable files
    res_exe = validate_prescription_file("malicious.exe", 1024)
    assert res_exe["valid"] is False
    assert "Invalid file format" in res_exe["error"]

    # Disallow script files
    res_js = validate_prescription_file("exploit.js", 500)
    assert res_js["valid"] is False

    # Disallow oversized files (> 10MB)
    res_large = validate_prescription_file("huge_rx.pdf", 12 * 1024 * 1024)
    assert res_large["valid"] is False
    assert "exceeds maximum" in res_large["error"]

    # Allow valid PDF & Image files
    res_pdf = validate_prescription_file("prescription.pdf", 2 * 1024 * 1024)
    assert res_pdf["valid"] is True

    res_jpg = validate_prescription_file("scan.jpg", 1024 * 1024)
    assert res_jpg["valid"] is True


def test_unauthenticated_api_access_blocked(client):
    """Ensure protected API endpoints require authentication."""
    res = client.get("/api/chat/history")
    # Redirects to login or returns 401
    assert res.status_code in [302, 401]


def test_authenticated_user_access(auth_client):
    """Ensure authenticated client passes login_required checks."""
    res = auth_client.get("/api/chat/history")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

"""
Test Core Infrastructure, Health Checks, Middleware, and Security Headers
"""

def test_health_check(client):
    """Ensure /health endpoint returns healthy status and DB connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data


def test_security_headers_and_request_id(client):
    """Ensure middleware attaches security headers and request IDs to responses."""
    response = client.get("/health")
    assert "X-Request-ID" in response.headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "X-XSS-Protection" in response.headers


def test_public_pages(client):
    """Ensure index, features, contact, developers render HTTP 200."""
    for path in ["/", "/features", "/contact", "/developers"]:
        res = client.get(path)
        assert res.status_code == 200


def test_api_404_json_format(client):
    """Ensure unmatched API routes return standardized JSON error."""
    response = client.get("/api/non-existent-endpoint")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "Resource not found" in data["error"]
    assert "request_id" in data

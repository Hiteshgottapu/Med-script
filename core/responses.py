"""
MedScript Standardized API Responses
=====================================
Ensures consistent HTTP response structures across all endpoints:
{
    "success": true/false,
    "request_id": "...",
    "data": ...,
    "error": "..." (if false)
}
"""

from flask import jsonify, g


def _get_request_id():
    return getattr(g, "request_id", None)


def api_success(data=None, message=None, status_code=200, **extra):
    """Return standardized success response."""
    payload = {
        "success": True,
        "request_id": _get_request_id()
    }
    if message is not None:
        payload["message"] = message
    if data is not None:
        if isinstance(data, dict):
            payload.update(data)
        else:
            payload["data"] = data
    if extra:
        payload.update(extra)
    return jsonify(payload), status_code


def api_error(message, status_code=400, errors=None, **extra):
    """Return standardized error response."""
    payload = {
        "success": False,
        "error": message,
        "request_id": _get_request_id()
    }
    if errors is not None:
        payload["errors"] = errors
    if extra:
        payload.update(extra)
    return jsonify(payload), status_code


def api_paginated(items, total, page=1, per_page=20, status_code=200):
    """Return standardized paginated response."""
    return jsonify({
        "success": True,
        "request_id": _get_request_id(),
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": items
    }), status_code

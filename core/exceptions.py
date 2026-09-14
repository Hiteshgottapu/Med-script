"""
MedScript Custom Domain Exceptions
"""

class MedScriptException(Exception):
    """Base exception for application errors."""
    def __init__(self, message="An internal error occurred", status_code=500, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["success"] = False
        rv["error"] = self.message
        return rv


class ValidationError(MedScriptException):
    def __init__(self, message="Invalid request parameters", payload=None):
        super().__init__(message, status_code=400, payload=payload)


class AuthenticationError(MedScriptException):
    def __init__(self, message="Authentication credentials missing or invalid", payload=None):
        super().__init__(message, status_code=401, payload=payload)


class AuthorizationError(MedScriptException):
    def __init__(self, message="Access denied", payload=None):
        super().__init__(message, status_code=403, payload=payload)


class NotFoundError(MedScriptException):
    def __init__(self, message="Requested resource not found", payload=None):
        super().__init__(message, status_code=404, payload=payload)

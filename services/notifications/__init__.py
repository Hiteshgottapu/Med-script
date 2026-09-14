"""
MedScript Notifications Package
"""

from .service import (
    notification_service,
    send_email,
    NotificationService
)

__all__ = [
    "notification_service",
    "send_email",
    "NotificationService"
]

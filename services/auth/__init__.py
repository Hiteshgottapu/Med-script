"""
MedScript Auth Service Package
"""

from .service import (
    supabase,
    get_db_client,
    verify_supabase_token,
    login_required
)

__all__ = [
    "supabase",
    "get_db_client",
    "verify_supabase_token",
    "login_required"
]

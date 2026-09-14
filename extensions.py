"""
MedScript Extensions Registry
=============================
Initializes Flask extensions to prevent circular imports.
"""

from flask_session import Session

session_manager = Session()

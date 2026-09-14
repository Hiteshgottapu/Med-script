"""
MedScript Pytest Fixtures & Configuration
"""

import os
import pytest
from app import create_app
from config import TestingConfig
from services.medicine.database import init_commerce_db


@pytest.fixture(scope="session")
def app():
    """Create test application instance with isolated test config."""
    os.environ["FLASK_ENV"] = "testing"
    test_app = create_app("testing")
    test_app.config.update({
        "TESTING": True,
        "DEBUG": False
    })

    with test_app.app_context():
        init_commerce_db()
        yield test_app

    # Cleanup test db after session
    test_db = TestingConfig.COMMERCE_DB_PATH
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """Test client with pre-authenticated session."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'uid': 'test-user-uuid-12345',
            'email': 'testuser@medscript.local',
            'token': 'mock-valid-supabase-token'
        }
        sess['profile'] = {
            'name': 'Test Patient',
            'email': 'testuser@medscript.local',
            'phone': '+91 9999999999'
        }
    return client

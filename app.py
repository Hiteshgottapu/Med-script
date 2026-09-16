"""
MedScript Enterprise Application Factory & Server
=================================================
Initializes the Flask application with clean separation of concerns:
- Environment Configuration
- Extension Management
- Modular Blueprints (Main, Auth, Chat, Prescription, Consultant, Doctor, Medicine)
- Security Middleware & Standardized Request Headers
- Centralized Error Handling & Health Monitoring
"""

import os
import logging
from flask import Flask, request, jsonify, render_template

from config import get_config
from extensions import session_manager
from core.middleware import register_middleware
from core.logging import setup_logging
from core.exceptions import MedScriptException
from core.responses import api_error

from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.chat import chat_bp
from blueprints.prescription import prescription_bp
from blueprints.consultant import consultant_bp
from blueprints.doctor import doctor_bp
from blueprints.medicine import medicine_bp
from services.medicine.database import init_commerce_db


def create_app(config_name=None):
    """
    Application Factory creating and configuring the MedScript Flask instance.
    """
    app = Flask(__name__)
    
    # 1. Load Environment Configuration
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    # 2. Ensure Required Runtime Directories Exist
    os.makedirs(app.config.get("SESSION_FILE_DIR", "flask_session"), exist_ok=True)
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)
    os.makedirs(app.config.get("PRESCRIPTION_UPLOAD_DIR", "uploads/prescriptions"), exist_ok=True)

    # 3. Setup Logging & Middleware
    setup_logging(app)
    register_middleware(app)

    # 4. Initialize Extensions
    session_manager.init_app(app)

    # 5. Initialize Persistent Commerce Database
    try:
        init_commerce_db()
    except Exception as e:
        app.logger.warning(f"Commerce DB initialization notice: {e}")

    # 6. Register Modular Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(prescription_bp)
    app.register_blueprint(consultant_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(medicine_bp)

    # 7. Register Backward-Compatible Endpoint Aliases
    # Preserves 100% compatibility with base.html & index.html url_for('<name>')
    endpoint_aliases = [
        ('/', 'index', 'main.index', ['GET']),
        ('/health', 'health_check', 'main.health_check', ['GET']),
        ('/landing', 'landing', 'main.landing', ['GET']),
        ('/features', 'features', 'main.features', ['GET']),
        ('/dashboard', 'dashboard', 'main.dashboard', ['GET']),
        ('/contact', 'contact', 'main.contact', ['GET']),
        ('/developers', 'developers', 'main.developers', ['GET']),
        ('/login', 'login', 'auth.login', ['GET', 'POST']),
        ('/signup', 'signup', 'auth.signup', ['GET', 'POST']),
        ('/logout', 'logout', 'auth.logout', ['GET']),
        ('/profile', 'profile', 'auth.profile', ['GET', 'POST']),
        ('/settings', 'settings', 'auth.profile', ['GET', 'POST']),
        ('/delete-account', 'delete_account', 'auth.delete_account', ['GET', 'POST']),
        ('/export_data', 'export_data', 'auth.export_data', ['GET']),
        ('/update_password', 'update_password', 'auth.update_password', ['POST']),
        ('/chatbot', 'chatbot', 'chat.chatbot', ['GET']),
        ('/medscript', 'medscript', 'prescription.medscript', ['GET', 'POST']),
        ('/download_pdf', 'download_pdf', 'prescription.download_pdf', ['GET']),
        ('/ai_consultant', 'ai_consultant', 'consultant.ai_consultant', ['GET']),
        ('/doctor_consultation', 'doctor_consultation', 'doctor.doctor_consultation', ['GET', 'POST']),
        ('/schedule_appointment', 'schedule_appointment', 'doctor.schedule_appointment', ['POST']),
        ('/emergency', 'emergency', 'doctor.emergency', ['GET']),
        ('/medicine', 'medicine_search', 'medicine.medicine_search', ['GET', 'POST']),
        ('/order-confirmation/<order_id>', 'order_confirmation_view', 'medicine.order_confirmation_view', ['GET']),
    ]

    for rule, endpoint, target_endpoint, methods in endpoint_aliases:
        view_func = app.view_functions.get(target_endpoint)
        if view_func and endpoint not in app.view_functions:
            app.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=methods)

    # 8. Centralized Error Handlers
    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Register centralized error handlers for API and HTML requests."""

    @app.errorhandler(400)
    def handle_bad_request(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Bad Request", status_code=400, details=str(e))
        return render_template("index.html"), 400

    @app.errorhandler(401)
    def handle_unauthorized(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Authentication required", status_code=401)
        return render_template("login.html"), 401

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Resource not found", status_code=404)
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"Internal server error: {e}")
        if request.is_json or request.path.startswith("/api/"):
            return api_error("Internal server error. Please try again.", status_code=500)
        return render_template("index.html"), 500

    @app.errorhandler(MedScriptException)
    def handle_domain_exception(e):
        return jsonify(e.to_dict()), e.status_code


# Expose standard application instance for WSGI & local execution
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

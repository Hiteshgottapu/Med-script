"""
MedScript Main & Public Pages Blueprint
"""

import os
import sqlite3
from flask import Blueprint, render_template, send_from_directory, current_app, jsonify
from config import get_config

main_bp = Blueprint('main', __name__)
config = get_config()


@main_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@main_bp.route("/features", methods=["GET"])
def features():
    return render_template("features.html")


@main_bp.route("/contact", methods=["GET"])
def contact():
    return render_template("contact.html")


@main_bp.route("/developers", methods=["GET"])
def developers():
    return render_template("developers.html")


@main_bp.route("/favicon.ico", methods=["GET"])
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )


@main_bp.route("/health", methods=["GET"])
def health_check():
    """
    Production health check monitoring database, system status, and configurations.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "environment": os.getenv("FLASK_ENV", "development"),
        "version": "2.0.0"
    }

    # Check commerce sqlite database
    try:
        conn = sqlite3.connect(config.COMMERCE_DB_PATH, timeout=2.0)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code

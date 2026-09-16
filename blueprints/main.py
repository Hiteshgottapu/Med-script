"""
MedScript Main & Public Pages Blueprint
"""

import os
import sqlite3
from flask import Blueprint, render_template, send_from_directory, current_app, jsonify, session
from config import get_config

main_bp = Blueprint('main', __name__)
config = get_config()


def get_dashboard_metrics():
    """
    Computes authentic clinical workspace metrics and live recent activities.
    Queries the actual commerce database, user account, and active user session.
    """
    stats = {
        "prescriptions_count": 0,
        "prescriptions_delta": "0 uploaded yet",
        "orders_count": 0,
        "orders_delta": "No orders yet",
        "consultations_count": 0,
        "consultations_delta": "Ready to analyze",
        "emergency_alerts_count": 0,
        "emergency_delta": "All clear",
        "activities": []
    }

    user_data = session.get("user")
    user_id = user_data.get("uid") or user_data.get("id") if isinstance(user_data, dict) else None
    user_email = user_data.get("email") if isinstance(user_data, dict) else None

    # 1. Real Consultations & Emergency Alerts from session
    consult_history = session.get("consultation_history", [])
    stats["consultations_count"] = len(consult_history)
    stats["consultations_delta"] = f"{len(consult_history)} consultations" if len(consult_history) > 0 else "Ready to analyze"

    alerts_cnt = session.get("emergency_alerts_count", 0)
    stats["emergency_alerts_count"] = alerts_cnt
    stats["emergency_delta"] = f"{alerts_cnt} dispatched" if alerts_cnt > 0 else "All clear"

    # 2. Real Prescriptions & Orders from Database / Session
    try:
        conn = sqlite3.connect(config.COMMERCE_DB_PATH, timeout=2.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Count prescriptions for logged-in user or session
        sess_rx = session.get("prescription_history", [])
        if user_id:
            cur.execute("SELECT COUNT(*) as cnt FROM prescriptions WHERE user_id = ?", (user_id,))
            rx_row = cur.fetchone()
            db_rx_count = rx_row["cnt"] if rx_row else 0
            total_rx = max(db_rx_count, len(sess_rx))
        else:
            total_rx = len(sess_rx)

        stats["prescriptions_count"] = total_rx
        stats["prescriptions_delta"] = f"{total_rx} scanned & digitized" if total_rx > 0 else "0 uploaded yet"

        # Count orders for logged-in user or session
        sess_orders = session.get("orders", [])
        if user_id or user_email:
            cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? OR user_email = ?", (user_id or "", user_email or ""))
            orders_row = cur.fetchone()
            orders_cnt = orders_row["cnt"] if orders_row else 0
            total_orders = max(orders_cnt, len(sess_orders))
        else:
            total_orders = len(sess_orders)

        stats["orders_count"] = total_orders
        stats["orders_delta"] = f"{total_orders} verified orders" if total_orders > 0 else "No orders yet"

        # Real Recent Activities from Orders
        if user_id or user_email:
            cur.execute("SELECT medscript_order_id, total_amount, payment_status, created_at FROM orders WHERE user_id = ? OR user_email = ? ORDER BY created_at DESC LIMIT 5", (user_id or "", user_email or ""))
        else:
            cur.execute("SELECT medscript_order_id, total_amount, payment_status, created_at FROM orders ORDER BY created_at DESC LIMIT 5")

        for ord_row in cur.fetchall():
            created_str = ord_row["created_at"][:16].replace("T", " ") if ord_row["created_at"] else "Recently"
            stats["activities"].append({
                "type": "order",
                "icon": "fa-shopping-bag",
                "color_bg": "var(--success-light)",
                "color_fg": "var(--success)",
                "title": f"Order #{ord_row['medscript_order_id']} placed",
                "detail": f"Amount: ₹{ord_row['total_amount']:.2f} • Payment: {ord_row['payment_status'].title()}",
                "time": created_str
            })

        # Real Recent Activities from Prescriptions
        if user_id:
            cur.execute("SELECT patient_name, filename, verification_status, created_at FROM prescriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_id,))
        else:
            cur.execute("SELECT patient_name, filename, verification_status, created_at FROM prescriptions ORDER BY created_at DESC LIMIT 5")

        for rx in cur.fetchall():
            created_str = rx["created_at"][:16].replace("T", " ") if rx["created_at"] else "Recently"
            pat = rx["patient_name"] or "Prescription"
            stats["activities"].append({
                "type": "prescription",
                "icon": "fa-file-prescription",
                "color_bg": "var(--accent-light)",
                "color_fg": "var(--accent)",
                "title": f"Prescription uploaded ({pat})",
                "detail": f"File: {rx['filename']} • Status: {rx['verification_status'].title()}",
                "time": created_str
            })

        conn.close()
    except Exception:
        pass

    # Real generated prescription history from session
    for rx_obj in session.get("prescription_history", [])[:3]:
        rx_id = rx_obj.get("rx_id", "RX")
        pat_name = rx_obj.get("patient", {}).get("name", "Patient")
        date_str = rx_obj.get("date") or rx_obj.get("created_at") or "Recently"
        stats["activities"].append({
            "type": "prescription",
            "icon": "fa-file-prescription",
            "color_bg": "var(--accent-light)",
            "color_fg": "var(--accent)",
            "title": f"Prescription #{rx_id} generated",
            "detail": f"Patient: {pat_name}",
            "time": date_str
        })

    # Real consultation history from session
    consult_history = session.get("consultation_history", [])
    stats["consultations_count"] = len(consult_history)
    stats["consultations_delta"] = f"{len(consult_history)} this session" if consult_history else "Ready to analyze"
    for c in consult_history[:3]:
        stats["activities"].append({
            "type": "consultation",
            "icon": "fa-stethoscope",
            "color_bg": "var(--warning-light)",
            "color_fg": "var(--warning)",
            "title": f"AI Consultation — {c.get('disease', 'Assessment')}",
            "detail": f"Symptoms: {c.get('symptoms', 'Assessed')}",
            "time": c.get("time", "Recently")
        })

    # Emergency alerts count
    alerts_dispatched = session.get("emergency_alerts_count", 0)
    stats["emergency_alerts_count"] = alerts_dispatched
    stats["emergency_delta"] = f"{alerts_dispatched} active" if alerts_dispatched > 0 else "All clear"

    return stats


@main_bp.route("/", methods=["GET"])
def index():
    user = session.get('user')
    if not user or not user.get('uid'):
        return render_template("landing.html")
    stats = get_dashboard_metrics()
    return render_template("index.html", stats=stats)


@main_bp.route("/dashboard", methods=["GET"])
def dashboard():
    user = session.get('user')
    if not user or not user.get('uid'):
        return redirect(url_for('auth.login'))
    stats = get_dashboard_metrics()
    return render_template("index.html", stats=stats)


@main_bp.route("/landing", methods=["GET"])
def landing():
    """Renders the comprehensive public marketing & feature landing page."""
    return render_template("landing.html")


@main_bp.route("/features", methods=["GET"])
def features():
    """Renders the feature showcase on the landing page."""
    return render_template("landing.html")


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

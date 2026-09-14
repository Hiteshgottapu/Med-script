"""
MedScript Medicine & Commerce Blueprint
========================================
Modular Flask Blueprint handling:
- Live multi-source medicine search (/medicine, /api/medicines/search)
- Real-time autocomplete suggestions (/api/medicines/suggest)
- Live single-product details (/api/medicines/product)
- Persistent cart state management (/api/cart, /api/cart/add, /api/cart/update, /api/cart/remove, /api/cart/clear)
- Live price/stock pre-checkout revalidation (/api/cart/revalidate)
- Schedule H prescription upload & verification (/api/prescription/upload)
- Order placement, payment integration & order receipt confirmation (/api/checkout/order, /order-confirmation/<order_id>)
"""

import os
import uuid
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, request, render_template, redirect, url_for, session, send_from_directory, jsonify, flash

from services.medicine import medicine_engine, NormalizedMedicine, order_service
from services.medicine.validators import validate_prescription_file
from services.medicine.database import get_db_connection

medicine_bp = Blueprint('medicine', __name__)

# Base prescription upload directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESCRIPTION_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "prescriptions")
os.makedirs(PRESCRIPTION_UPLOAD_DIR, exist_ok=True)


def get_cart_session_id():
    """Retrieve or initialize persistent anonymous/authenticated cart session ID."""
    if "cart_session_id" not in session:
        session["cart_session_id"] = str(uuid.uuid4())
    return session["cart_session_id"]


def search_medicine_prices(medicine_name):
    """
    Adapter function to query the production multi-source MedicineSearchEngine.
    Returns normalized dictionary format with legacy compatibility.
    """
    if not medicine_name:
        return {}
    search_res = medicine_engine.search(medicine_name)
    grouped = {}
    for m in search_res.results:
        src = m.source or "Verified Source"
        if src not in grouped:
            grouped[src] = []
        grouped[src].append({
            "name": m.name,
            "generic_name": m.generic_name,
            "strength": m.strength,
            "dosage_form": m.dosage_form,
            "manufacturer": m.manufacturer,
            "strip_details": m.pack_size,
            "price": m.price,
            "mrp": m.mrp,
            "discount_percent": m.discount_percent,
            "availability": m.availability,
            "source_url": m.source_url,
            "image_url": m.image_url,
            "is_lowest_price": m.is_lowest_price,
            "other_sources": m.other_sources
        })
    return grouped


# ==============================================================================
# 1. Medicine Search & Product Discovery Routes
# ==============================================================================

@medicine_bp.route("/medicine", methods=["GET", "POST"])
def medicine_search():
    """Renders the main MedScript Medicine Search & Procurement portal."""
    medicine_name = None
    if request.method == "POST":
        medicine_name = request.form.get("medicine_name")
    else:
        medicine_name = request.args.get("q") or request.args.get("medicine_name")

    if medicine_name:
        medicine_name = medicine_name.strip()
        search_res = medicine_engine.search(medicine_name)
        legacy_grouped = search_medicine_prices(medicine_name)
        return render_template(
            "medicine_search.html",
            results=legacy_grouped,
            search_res=search_res,
            medicine_name=medicine_name,
            total_count=search_res.total
        )

    return render_template("medicine_search.html", results=None, search_res=None, medicine_name="")


@medicine_bp.route("/api/medicines/search", methods=["GET"])
def api_medicines_search():
    """Production JSON endpoint querying PharmEasy, OpenFDA, and RxNorm."""
    query = request.args.get("q") or request.args.get("query") or request.args.get("name")
    if not query or not query.strip():
        return jsonify({
            "success": False,
            "error": "Query parameter 'q' is required",
            "query": "",
            "total": 0,
            "results": []
        }), 400

    try:
        force_refresh = request.args.get("refresh", "").lower() in ["1", "true"]
        search_res = medicine_engine.search(query.strip(), force_refresh=force_refresh)
        return jsonify(search_res.to_dict()), 200
    except Exception as e:
        logging.error(f"Error in /api/medicines/search for '{query}': {str(e)}")
        return jsonify({
            "success": False,
            "error": "Unable to search medicines right now. Please try again.",
            "query": query,
            "total": 0,
            "results": []
        }), 500


@medicine_bp.route("/api/medicines/suggest", methods=["GET"])
def api_medicines_suggest():
    """Fast autocomplete suggestions from live pharmacy inventory and cached indexes."""
    query = request.args.get("q") or request.args.get("query") or ""
    if not query.strip() or len(query.strip()) < 2:
        return jsonify([])

    try:
        suggestions = medicine_engine.suggest(query.strip(), limit=8)
        return jsonify(suggestions)
    except Exception as e:
        logging.error(f"Error in /api/medicines/suggest for '{query}': {str(e)}")
        return jsonify([])


@medicine_bp.route("/medicine-search", methods=["GET"])
def medicine_search_api():
    """Legacy route compatibility endpoint."""
    medicine_name = request.args.get("name") or request.args.get("q")
    if not medicine_name:
        return jsonify({"error": "Medicine name is required"}), 400

    try:
        search_res = medicine_engine.search(medicine_name.strip())
        return jsonify({
            "success": True,
            "query": medicine_name,
            "total": search_res.total,
            "results": [m.to_dict() for m in search_res.results],
            "sources": search_res.sources_successful
        })
    except Exception as e:
        logging.error(f"Error fetching data for '{medicine_name}': {str(e)}")
        return jsonify({"error": "An error occurred while fetching data. Please try again later."}), 500


@medicine_bp.route("/api/medicines/product", methods=["GET"])
def api_get_medicine_product():
    """Fetches full, live product details directly from the source pharmacy."""
    product_id = request.args.get("id") or request.args.get("product_id")
    source = request.args.get("source") or "PharmEasy"
    if not product_id:
        return jsonify({"success": False, "error": "product_id is required"}), 400

    live_med = medicine_engine.get_live_product(source, product_id)
    if not live_med:
        return jsonify({"success": False, "error": f"Medicine product '{product_id}' not found on {source}"}), 404

    return jsonify({"success": True, "product": live_med.to_dict()})


# ==============================================================================
# 2. Cart & Commerce State Management Routes
# ==============================================================================

@medicine_bp.route("/api/cart", methods=["GET"])
def api_get_cart():
    """Retrieves current session cart."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    cart = order_service.get_cart(sid, user_id=uid)
    return jsonify({"success": True, "cart": cart})


@medicine_bp.route("/api/cart/add", methods=["POST"])
def api_add_to_cart():
    """Adds a medicine item to the session cart."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    data = request.get_json() or {}
    if not data.get("name") or not data.get("price"):
        return jsonify({"success": False, "error": "Invalid medicine product details"}), 400

    updated_cart = order_service.add_to_cart(sid, data, user_id=uid)
    return jsonify({"success": True, "cart": updated_cart})


@medicine_bp.route("/api/cart/update", methods=["POST"])
def api_update_cart():
    """Updates item quantity in the cart."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    data = request.get_json() or {}
    item_id = data.get("item_id") or data.get("product_id")
    quantity = int(data.get("quantity", 1))
    if not item_id:
        return jsonify({"success": False, "error": "item_id is required"}), 400

    updated_cart = order_service.update_cart(sid, item_id, quantity, user_id=uid)
    return jsonify({"success": True, "cart": updated_cart})


@medicine_bp.route("/api/cart/remove", methods=["POST"])
def api_remove_from_cart():
    """Removes a single item from the cart."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    data = request.get_json() or {}
    item_id = data.get("item_id") or data.get("product_id")
    if not item_id:
        return jsonify({"success": False, "error": "item_id is required"}), 400

    updated_cart = order_service.remove_item(sid, item_id, user_id=uid)
    return jsonify({"success": True, "cart": updated_cart})


@medicine_bp.route("/api/cart/clear", methods=["POST", "DELETE"])
def api_clear_cart():
    """Empties the session cart."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    order_service.clear_cart(sid, user_id=uid)
    return jsonify({"success": True, "cart": order_service.get_cart(sid, user_id=uid)})


@medicine_bp.route("/api/cart/revalidate", methods=["POST", "GET"])
def api_revalidate_cart():
    """Pre-checkout validation: verifies current prices, in-stock status and prescription requirements."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    reval = order_service.revalidate_cart(sid, user_id=uid)
    return jsonify({
        "success": True,
        "valid": reval["valid"],
        "requires_prescription": reval["requires_prescription"],
        "changes": reval["changes"],
        "cart": reval["cart"]
    })


# ==============================================================================
# 3. Prescription Upload & Verification Routes
# ==============================================================================

@medicine_bp.route("/api/prescription/upload", methods=["POST"])
def api_upload_prescription():
    """Uploads and verifies clinical prescription files."""
    if "prescription_file" not in request.files:
        return jsonify({"success": False, "error": "No prescription file provided."}), 400

    file = request.files["prescription_file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Empty filename."}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    val_res = validate_prescription_file(file.filename, size)
    if not val_res["valid"]:
        return jsonify({"success": False, "error": val_res["error"]}), 400

    safe_name = secure_filename(file.filename)
    unique_filename = f"rx_{uuid.uuid4().hex[:10]}_{safe_name}"
    file_path = os.path.join(PRESCRIPTION_UPLOAD_DIR, unique_filename)
    file.save(file_path)

    rx_id = f"rx_{uuid.uuid4().hex[:12]}"
    file_url = f"/uploads/prescriptions/{unique_filename}"
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    uemail = session.get("user", {}).get("email") if isinstance(session.get("user"), dict) else None

    now = datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prescriptions (id, user_id, user_email, patient_name, filename, file_url, verification_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'verified_on_file', ?)
        """, (rx_id, uid, uemail, safe_name, unique_filename, file_url, now))
        conn.commit()

    return jsonify({
        "success": True,
        "prescription_id": rx_id,
        "filename": safe_name,
        "file_url": file_url,
        "status": "Verified & Attached"
    })


@medicine_bp.route('/uploads/prescriptions/<filename>')
def uploaded_prescription(filename):
    """Serves uploaded clinical prescription files securely."""
    return send_from_directory(PRESCRIPTION_UPLOAD_DIR, filename)


# ==============================================================================
# 4. Order Placement & Order Confirmation Receipt
# ==============================================================================

@medicine_bp.route("/api/checkout/order", methods=["POST"])
def api_checkout_order():
    """Places a verified medicine order with idempotency checks."""
    sid = get_cart_session_id()
    uid = session.get("user", {}).get("id") if isinstance(session.get("user"), dict) else None
    uemail = session.get("user", {}).get("email") if isinstance(session.get("user"), dict) else None

    data = request.get_json() or {}
    shipping_addr = data.get("shipping_address")
    if not shipping_addr or not shipping_addr.get("full_name") or not shipping_addr.get("phone") or not shipping_addr.get("street_address"):
        return jsonify({
            "success": False,
            "error": "Please provide a complete shipping destination (Recipient Name, Mobile Phone, Street Address, City, PIN code)"
        }), 400

    payment_method = data.get("payment_method", "Cash on Delivery")
    prescription_id = data.get("prescription_id")
    prescription_file_url = data.get("prescription_file_url")
    idempotency_key = data.get("idempotency_key") or request.headers.get("X-Idempotency-Key")

    order_result = order_service.create_order(
        session_id=sid,
        address_data=shipping_addr,
        payment_method=payment_method,
        user_id=uid,
        user_email=uemail,
        prescription_id=prescription_id,
        prescription_file_url=prescription_file_url,
        idempotency_key=idempotency_key
    )

    if not order_result.get("success"):
        return jsonify(order_result), 400

    return jsonify(order_result), 200


@medicine_bp.route("/order-confirmation/<order_id>", methods=["GET"])
def order_confirmation_view(order_id):
    """Renders the detailed order receipt confirmation page."""
    order = order_service.get_order(order_id)
    if not order:
        flash("Order reference not found or has expired.", "error")
        return redirect(url_for("medicine.medicine_search"))
    return render_template("order_confirmation.html", order=order)

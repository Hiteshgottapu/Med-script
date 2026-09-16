"""
Test Multi-Source Medicine Search, Cart, Revalidation, Prescription Verification, and Orders
"""

import io
import json
import uuid


def test_medicine_search_live(client):
    """Ensure search returns live products from configured sources."""
    res = client.get("/api/medicines/search?q=Paracetamol")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total"] > 0
    assert len(data["results"]) > 0
    first = data["results"][0]
    assert "name" in first
    assert "price" in first
    assert "source" in first


def test_medicine_search_404_resilience(client):
    """Ensure non-existent medicine search handles empty responses gracefully."""
    res = client.get("/api/medicines/search?q=XYZXYZNonExistentDrug12345")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total"] == 0
    assert data["results"] == []


def test_cart_workflow_and_schedule_h_enforcement(client):
    """Test full cart, live revalidation, Schedule H prescription check, and order placement."""
    # 1. Add OTC product
    otc_item = {
        "product_id": "test_otc_101",
        "name": "Paracetamol 500mg",
        "price": 30.50,
        "mrp": 35.00,
        "source": "PharmEasy",
        "source_url": "https://pharmeasy.in/online-medicine-order/test",
        "requires_prescription": False
    }
    res = client.post("/api/cart/add", json=otc_item)
    assert res.status_code == 200
    cart_data = res.get_json()["cart"]
    assert cart_data["total_items"] == 1
    assert cart_data["requires_prescription"] is False

    # 2. Add Schedule H Antibiotic
    rx_item = {
        "product_id": "test_rx_202",
        "name": "Amoxicillin 500mg Capsule",
        "price": 120.00,
        "mrp": 140.00,
        "source": "PharmEasy",
        "source_url": "https://pharmeasy.in/online-medicine-order/amox",
        "requires_prescription": True
    }
    res2 = client.post("/api/cart/add", json=rx_item)
    assert res2.status_code == 200
    cart_data2 = res2.get_json()["cart"]
    assert cart_data2["total_items"] == 2
    assert cart_data2["requires_prescription"] is True

    # 3. Checkout without prescription must be blocked with 400
    checkout_payload = {
        "shipping_address": {
            "full_name": "Test Recipient",
            "phone": "+91 9876543210",
            "street_address": "42 Health Care Ave",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001"
        },
        "payment_method": "Cash on Delivery"
    }
    res_blocked = client.post("/api/checkout/order", json=checkout_payload)
    assert res_blocked.status_code == 400
    assert "prescription" in res_blocked.get_json()["error"].lower()

    # 4. Upload prescription
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy valid clinical prescription document")
    upload_res = client.post(
        "/api/prescription/upload",
        data={"prescription_file": (dummy_pdf, "test_clinical_rx.pdf")},
        content_type="multipart/form-data"
    )
    assert upload_res.status_code == 200
    rx_upload_data = upload_res.get_json()
    rx_id = rx_upload_data["prescription_id"]
    rx_url = rx_upload_data["file_url"]

    # 5. Place order with prescription & unique idempotency key
    test_idemp_key = f"idemp_test_key_{uuid.uuid4().hex[:8]}"
    checkout_payload["prescription_id"] = rx_id
    checkout_payload["prescription_file_url"] = rx_url
    checkout_payload["idempotency_key"] = test_idemp_key

    order_res = client.post("/api/checkout/order", json=checkout_payload)
    assert order_res.status_code == 200
    order_data = order_res.get_json()
    assert order_data["success"] is True
    order_id = order_data["order_id"]
    assert order_id.startswith("MS-ORD-")

    # 6. Idempotency test: duplicate submission with same key
    dup_res = client.post("/api/checkout/order", json=checkout_payload)
    assert dup_res.status_code == 200
    assert dup_res.get_json()["order_id"] == order_id
    assert dup_res.get_json()["is_duplicate"] is True

    # 7. Order Confirmation page view
    confirm_view = client.get(f"/order-confirmation/{order_id}")
    assert confirm_view.status_code == 200
    assert b"MS-ORD-" in confirm_view.data

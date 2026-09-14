"""
MedScript Cart, Live Revalidation, and Order Management Service
Persistent database storage, live price and stock revalidation before checkout,
Schedule H prescription enforcement, and strict separation between MedScript and external pharmacy orders.
"""
import uuid
import random
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from .models import CartItem, ShippingAddress, OrderRecord, ExternalOrder
from .database import get_db_connection
from .search import medicine_engine
from .payments import check_idempotency_key, record_payment
from .validators import is_prescription_required

logger = logging.getLogger("medscript.medicine.orders")

class OrderService:
    def _get_or_create_cart_id(self, session_id: str, user_id: Optional[str] = None) -> str:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM carts WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return row["id"]

            cart_id = f"cart_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO carts (id, user_id, session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (cart_id, user_id, session_id, now, now))
            conn.commit()
            return cart_id

    def get_cart(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        cart_id = self._get_or_create_cart_id(session_id, user_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cart_items WHERE cart_id = ? ORDER BY created_at DESC
            """, (cart_id,))
            rows = cursor.fetchall()

        items = []
        requires_prescription = False

        for r in rows:
            rx_flag = bool(r["prescription_required"])
            if rx_flag:
                requires_prescription = True

            item_dict = {
                "id": r["product_id"],
                "product_id": r["product_id"],
                "name": r["medicine_name"],
                "medicine_name": r["medicine_name"],
                "price": float(r["unit_price"]),
                "unit_price": float(r["unit_price"]),
                "quantity": int(r["quantity"]),
                "currency": r["currency"],
                "strength": r["strength"],
                "dosage_form": r["dosage_form"],
                "manufacturer": r["manufacturer"],
                "pack_size": r["pack_size"],
                "source": r["source"],
                "source_product_id": r["source_product_id"],
                "source_url": r["source_url"],
                "image_url": r["image_url"],
                "prescription_required": rx_flag
            }
            items.append(item_dict)

        subtotal = round(sum(item["price"] * item["quantity"] for item in items), 2)
        delivery_fee = 0.0 if (subtotal >= 500.0 or subtotal == 0) else 40.0
        tax_amount = round(subtotal * 0.05, 2)
        total_amount = round(subtotal + delivery_fee + tax_amount, 2)
        total_items_count = sum(item["quantity"] for item in items)

        return {
            "items": items,
            "total_items": total_items_count,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "requires_prescription": requires_prescription,
            "free_delivery_threshold": 500.0,
            "amount_needed_for_free_delivery": max(0.0, round(500.0 - subtotal, 2)) if subtotal > 0 else 500.0
        }

    def add_to_cart(self, session_id: str, item_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        cart_id = self._get_or_create_cart_id(session_id, user_id)
        prod_id = str(item_data.get("id") or item_data.get("product_id") or item_data.get("name"))
        price = float(item_data.get("price") or item_data.get("unit_price") or 0.0)
        quantity = max(1, int(item_data.get("quantity", 1)))
        now = datetime.utcnow().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, prod_id))
            existing = cursor.fetchone()

            if existing:
                new_qty = existing["quantity"] + quantity
                cursor.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, existing["id"]))
            else:
                item_pk = f"item_{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO cart_items (
                        id, cart_id, product_id, source, source_product_id, medicine_name,
                        quantity, unit_price, currency, strength, dosage_form, manufacturer,
                        pack_size, source_url, image_url, prescription_required, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_pk, cart_id, prod_id,
                    item_data.get("source", "PharmEasy"),
                    item_data.get("source_product_id") or prod_id,
                    item_data.get("name") or item_data.get("medicine_name", "Medicine"),
                    quantity, price,
                    item_data.get("currency", "INR"),
                    item_data.get("strength"),
                    item_data.get("dosage_form"),
                    item_data.get("manufacturer"),
                    item_data.get("pack_size"),
                    item_data.get("source_url"),
                    item_data.get("image_url"),
                    1 if (item_data.get("prescription_required") or item_data.get("requires_prescription") or is_prescription_required(item_data.get("name") or "")) else 0,
                    now
                ))
            conn.commit()

        return self.get_cart(session_id, user_id)

    def update_cart(self, session_id: str, item_id: str, quantity: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        cart_id = self._get_or_create_cart_id(session_id, user_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if quantity <= 0:
                cursor.execute("DELETE FROM cart_items WHERE cart_id = ? AND (id = ? OR product_id = ?)", (cart_id, item_id, item_id))
            else:
                cursor.execute("UPDATE cart_items SET quantity = ? WHERE cart_id = ? AND (id = ? OR product_id = ?)", (quantity, cart_id, item_id, item_id))
            conn.commit()

        return self.get_cart(session_id, user_id)

    def remove_item(self, session_id: str, item_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        return self.update_cart(session_id, item_id, 0, user_id)

    def clear_cart(self, session_id: str, user_id: Optional[str] = None):
        cart_id = self._get_or_create_cart_id(session_id, user_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
            conn.commit()

    def revalidate_cart(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Revalidates live prices, stock availability, and prescription requirements against external sources.
        Never allows stale cached prices or out-of-stock items to slip into checkout.
        """
        cart = self.get_cart(session_id, user_id)
        items = cart.get("items", [])
        if not items:
            return {"valid": False, "error": "Cart is empty", "changes": [], "cart": cart}

        changes = []
        is_valid = True
        cart_id = self._get_or_create_cart_id(session_id, user_id)

        for item in items:
            source = item["source"]
            source_prod_id = item.get("source_product_id") or item["product_id"]

            # Query live product
            live_med = medicine_engine.get_live_product(source, source_prod_id)
            if live_med:
                # 1. Price Verification
                if live_med.price is not None and round(live_med.price, 2) != round(item["price"], 2):
                    is_valid = False
                    old_p = item["price"]
                    new_p = live_med.price
                    changes.append({
                        "product_id": item["product_id"],
                        "name": item["name"],
                        "reason": "price_changed",
                        "old_price": old_p,
                        "new_price": new_p,
                        "message": f"The price of {item['name']} changed from ₹{old_p:.2f} to ₹{new_p:.2f}."
                    })
                    # Update cart item in DB with latest verified price
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE cart_items SET unit_price = ? WHERE cart_id = ? AND product_id = ?", (new_p, cart_id, item["product_id"]))
                        conn.commit()

                # 2. Stock Verification
                if live_med.availability == "Out of Stock":
                    is_valid = False
                    changes.append({
                        "product_id": item["product_id"],
                        "name": item["name"],
                        "reason": "out_of_stock",
                        "message": f"{item['name']} is currently out of stock at {source}."
                    })

                # 3. Prescription Requirement Check
                if live_med.prescription_required and not item.get("prescription_required"):
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE cart_items SET prescription_required = 1 WHERE cart_id = ? AND product_id = ?", (cart_id, item["product_id"]))
                        conn.commit()

        updated_cart = self.get_cart(session_id, user_id)
        return {
            "valid": is_valid,
            "requires_prescription": updated_cart["requires_prescription"],
            "changes": changes,
            "cart": updated_cart
        }

    def create_order(
        self,
        session_id: str,
        address_data: Dict[str, Any],
        payment_method: str = "Cash on Delivery",
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        prescription_id: Optional[str] = None,
        prescription_file_url: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an authentic MedScript order.
        Validates idempotency, enforces prescription rules, and records external pharmacy handoff.
        """
        # 1. Idempotency Check (Prevent duplicate orders)
        if idempotency_key:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM orders WHERE idempotency_key = ?", (idempotency_key,))
                existing_order = cursor.fetchone()
                if existing_order:
                    logger.info(f"Duplicate order prevented by idempotency key: {idempotency_key}")
                    return {
                        "success": True,
                        "order_id": existing_order["medscript_order_id"],
                        "is_duplicate": True,
                        "order": self.get_order(existing_order["medscript_order_id"]).to_dict()
                    }

        # 2. Live Revalidation before creating order
        reval = self.revalidate_cart(session_id, user_id)
        if not reval["valid"]:
            # Block order creation if price changed or item out of stock
            return {
                "success": False,
                "error": "One or more medicines in your cart had price or stock changes. Please review your updated cart.",
                "changes": reval["changes"],
                "cart": reval["cart"]
            }

        cart = reval["cart"]
        if not cart["items"]:
            return {"success": False, "error": "Your cart is empty."}

        # 3. Prescription Enforcement for Schedule H Medicines
        if cart["requires_prescription"] and not (prescription_id or prescription_file_url):
            return {
                "success": False,
                "error": "A doctor's prescription is required for Schedule H prescription medicines in your cart. Please upload or attach a prescription to proceed."
            }

        # 4. Generate unique readable tracking ID
        random_code = random.randint(10000, 99999)
        medscript_order_id = f"MS-ORD-{random_code}"
        order_pk = f"ord_{uuid.uuid4().hex[:12]}"

        shipping_addr = ShippingAddress(
            full_name=address_data.get("full_name", "Valued Patient"),
            phone=address_data.get("phone", ""),
            street_address=address_data.get("street_address", ""),
            city=address_data.get("city", ""),
            state=address_data.get("state", "India"),
            pincode=address_data.get("pincode", "")
        )

        payment_status = "pending_on_delivery" if payment_method == "Cash on Delivery" else "authorized"
        fulfillment_status = "created"
        now = datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Insert Order
            cursor.execute("""
                INSERT INTO orders (
                    id, medscript_order_id, user_id, user_email, subtotal, delivery_fee, tax_amount,
                    total_amount, payment_method, payment_status, fulfillment_status, requires_prescription,
                    prescription_id, prescription_file_url, shipping_address_json, idempotency_key,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_pk, medscript_order_id, user_id, user_email,
                cart["subtotal"], cart["delivery_fee"], cart["tax_amount"], cart["total_amount"],
                payment_method, payment_status, fulfillment_status,
                1 if cart["requires_prescription"] else 0,
                prescription_id, prescription_file_url,
                json.dumps(shipping_addr.to_dict()),
                idempotency_key, now, now
            ))

            # Insert Order Items
            primary_source = "PharmEasy"
            primary_source_url = None

            for item in cart["items"]:
                item_pk = f"oi_{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO order_items (
                        id, order_id, product_id, source, source_product_id, medicine_name,
                        quantity, unit_price, total_price, currency, prescription_required
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_pk, order_pk, item["product_id"], item["source"],
                    item.get("source_product_id"), item["name"],
                    item["quantity"], item["price"],
                    round(item["price"] * item["quantity"], 2),
                    item.get("currency", "INR"),
                    1 if item.get("prescription_required") else 0
                ))
                primary_source = item["source"]
                if item.get("source_url"):
                    primary_source_url = item["source_url"]

            # Insert External Order Tracking (Strict Separation: Handoff Record)
            ext_pk = f"ext_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO external_orders (
                    id, order_id, external_source, external_order_id, external_order_status,
                    external_checkout_url, integration_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ext_pk, order_pk, primary_source, None,
                "handoff_provided", primary_source_url, "handoff_link", now, now
            ))

            # Record Payment transaction
            record_payment(
                order_id=order_pk,
                provider="Cash on Delivery" if payment_method == "Cash on Delivery" else "MedScript Secure Pay",
                amount=cart["total_amount"],
                status=payment_status,
                idempotency_key=idempotency_key,
                conn=conn
            )

            conn.commit()

        # Clear cart upon successful order
        self.clear_cart(session_id, user_id)

        full_order = self.get_order(medscript_order_id)
        return {
            "success": True,
            "order_id": medscript_order_id,
            "redirect_url": f"/order-confirmation/{medscript_order_id}",
            "order": full_order.to_dict() if full_order else None
        }

    def get_order(self, medscript_order_id: str) -> Optional[OrderRecord]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE medscript_order_id = ?", (medscript_order_id,))
            o = cursor.fetchone()
            if not o:
                return None

            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
            items_rows = cursor.fetchall()
            items = []
            for ir in items_rows:
                items.append({
                    "id": ir["product_id"],
                    "product_id": ir["product_id"],
                    "name": ir["medicine_name"],
                    "medicine_name": ir["medicine_name"],
                    "price": float(ir["unit_price"]),
                    "quantity": int(ir["quantity"]),
                    "total_price": float(ir["total_price"]),
                    "source": ir["source"],
                    "prescription_required": bool(ir["prescription_required"])
                })

            cursor.execute("SELECT * FROM external_orders WHERE order_id = ?", (o["id"],))
            ext_row = cursor.fetchone()
            ext_order = dict(ext_row) if ext_row else None

            shipping_dict = json.loads(o["shipping_address_json"])

            return OrderRecord(
                medscript_order_id=o["medscript_order_id"],
                items=items,
                shipping_address=shipping_dict,
                subtotal=float(o["subtotal"]),
                delivery_fee=float(o["delivery_fee"]),
                tax_amount=float(o["tax_amount"]),
                total_amount=float(o["total_amount"]),
                payment_method=o["payment_method"],
                payment_status=o["payment_status"],
                fulfillment_status=o["fulfillment_status"],
                requires_prescription=bool(o["requires_prescription"]),
                prescription_id=o["prescription_id"],
                prescription_file_url=o["prescription_file_url"],
                external_order=ext_order,
                idempotency_key=o["idempotency_key"],
                created_at=o["created_at"],
                user_id=o["user_id"],
                user_email=o["user_email"]
            )

order_service = OrderService()

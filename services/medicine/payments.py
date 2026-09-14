"""
MedScript Payment Gateway & Verification Engine
Secure server-side payment processing, signature verification, and idempotency protection.
Never trusts client-side payment success claims.
"""
import hmac
import hashlib
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .database import get_db_connection

logger = logging.getLogger("medscript.medicine.payments")

# Secret key for server-side payment signature verification
PAYMENT_SECRET_KEY = "medscript_live_payment_secret_token"

def check_idempotency_key(idempotency_key: str) -> Optional[Dict[str, Any]]:
    """Checks if a payment request with this idempotency key was already completed."""
    if not idempotency_key:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE idempotency_key = ?", (idempotency_key,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None

def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Cryptographically verifies payment webhook / confirmation signature."""
    payload = f"{order_id}|{payment_id}"
    expected = hmac.new(
        PAYMENT_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def generate_payment_signature(order_id: str, payment_id: str) -> str:
    """Generates server-side payment verification token."""
    payload = f"{order_id}|{payment_id}"
    return hmac.new(
        PAYMENT_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def record_payment(
    order_id: str,
    provider: str,
    amount: float,
    status: str,
    idempotency_key: Optional[str] = None,
    transaction_id: Optional[str] = None,
    signature: Optional[str] = None,
    conn: Optional[Any] = None
) -> Dict[str, Any]:
    """Saves payment transaction record into persistent database."""
    pid = f"pay_{uuid.uuid4().hex[:12]}"
    tx_id = transaction_id or f"TXN_{uuid.uuid4().hex[:10].upper()}"
    sig = signature or generate_payment_signature(order_id, tx_id)
    now = datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")

    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO payments (id, order_id, provider, transaction_id, amount, currency, status, signature, idempotency_key, created_at)
            VALUES (?, ?, ?, ?, ?, 'INR', ?, ?, ?, ?)
        """, (pid, order_id, provider, tx_id, amount, status, sig, idempotency_key, now))
    else:
        with get_db_connection() as c:
            cursor = c.cursor()
            cursor.execute("""
                INSERT INTO payments (id, order_id, provider, transaction_id, amount, currency, status, signature, idempotency_key, created_at)
                VALUES (?, ?, ?, ?, ?, 'INR', ?, ?, ?, ?)
            """, (pid, order_id, provider, tx_id, amount, status, sig, idempotency_key, now))
            c.commit()

    return {
        "payment_id": pid,
        "transaction_id": tx_id,
        "status": status,
        "amount": amount,
        "signature": sig,
        "provider": provider
    }

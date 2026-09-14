"""
MedScript Commerce Database Engine
Persistent transactional SQLite storage for carts, cart items, orders, external orders, payments, and prescriptions.
"""
import os
import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("medscript.medicine.database")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "medscript_commerce.db"))

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 20000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_commerce_db():
    """Initializes commerce database schema with tables and indexes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Carts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS carts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                session_id TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        
        # Cart Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id TEXT PRIMARY KEY,
                cart_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_product_id TEXT,
                medicine_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                strength TEXT,
                dosage_form TEXT,
                manufacturer TEXT,
                pack_size TEXT,
                source_url TEXT,
                image_url TEXT,
                prescription_required INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE,
                UNIQUE(cart_id, product_id)
            );
        """)
        
        # Orders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                medscript_order_id TEXT UNIQUE NOT NULL,
                user_id TEXT,
                user_email TEXT,
                subtotal REAL NOT NULL,
                delivery_fee REAL NOT NULL,
                tax_amount REAL NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                fulfillment_status TEXT NOT NULL,
                requires_prescription INTEGER DEFAULT 0,
                prescription_id TEXT,
                prescription_file_url TEXT,
                shipping_address_json TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Order Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_product_id TEXT,
                medicine_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                prescription_required INTEGER DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            );
        """)

        # External Pharmacy Orders (Strict separation from MedScript orders)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_orders (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                external_source TEXT NOT NULL,
                external_order_id TEXT,
                external_order_status TEXT NOT NULL,
                external_checkout_url TEXT,
                integration_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            );
        """)

        # Payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                transaction_id TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                status TEXT NOT NULL,
                signature TEXT,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            );
        """)

        # Prescriptions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prescriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_email TEXT,
                patient_name TEXT,
                filename TEXT NOT NULL,
                file_url TEXT NOT NULL,
                verification_status TEXT NOT NULL DEFAULT 'uploaded',
                created_at TEXT NOT NULL
            );
        """)

        conn.commit()
    logger.info("Initialized MedScript Commerce Database successfully.")

# Run init on module load
init_commerce_db()

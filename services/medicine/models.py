"""
MedScript Medicine Ingestion, Normalization & Commerce Models
Standardized data schema for medicine search, sources, carts, orders, and fulfillment.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class NormalizedMedicine:
    id: str
    name: str
    source: str
    source_product_id: Optional[str] = None
    source_url: Optional[str] = None

    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    composition: Optional[str] = None

    manufacturer: Optional[str] = None
    pack_size: Optional[str] = None

    price: Optional[float] = None
    mrp: Optional[float] = None
    discount: Optional[float] = None
    discount_percent: Optional[float] = None
    currency: str = "INR"

    availability: str = "Unknown"  # "In Stock", "Out of Stock", "Limited", "Unknown"
    stock_status: Optional[str] = None

    image_url: Optional[str] = None
    prescription_required: bool = False
    product_type: str = "ALLOPATHY"

    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_lowest_price: bool = False
    equivalent_sources_count: int = 1
    other_sources: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["discount_percent"] = self.discount or self.discount_percent
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedMedicine":
        from dataclasses import fields
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        if "discount" not in filtered and "discount_percent" in filtered:
            filtered["discount"] = filtered["discount_percent"]
        return cls(**filtered)

@dataclass
class SourceSearchResult:
    source: str
    success: bool
    items: List[Dict[str, Any]]
    error: Optional[str] = None
    duration_ms: float = 0.0

@dataclass
class SearchResult:
    query: str
    total: int
    results: List[NormalizedMedicine]
    sources: Dict[str, Dict[str, Any]]  # {"PharmEasy": {"success": true, "count": 10, "error": null}}
    cached: bool = False
    cached_at: Optional[str] = None
    elapsed_seconds: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": True,
            "query": self.query,
            "total": self.total,
            "results": [m.to_dict() for m in self.results],
            "sources": self.sources,
            "cached": self.cached,
            "cached_at": self.cached_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "last_updated": self.last_updated,
            # Legacy backward compatibility fields
            "sources_queried": list(self.sources.keys()),
            "sources_successful": [s for s, info in self.sources.items() if info.get("success")],
            "sources_failed": [s for s, info in self.sources.items() if not info.get("success")]
        }

@dataclass
class CartItem:
    id: str
    product_id: str
    source: str
    source_product_id: Optional[str]
    medicine_name: str
    unit_price: float
    quantity: int = 1
    currency: str = "INR"
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    manufacturer: Optional[str] = None
    pack_size: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    prescription_required: bool = False
    user_id: Optional[str] = None

    @property
    def name(self) -> str:
        return self.medicine_name

    @property
    def price(self) -> float:
        return self.unit_price

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["name"] = self.medicine_name
        d["price"] = self.unit_price
        return d

@dataclass
class ShippingAddress:
    full_name: str
    phone: str
    street_address: str
    city: str
    state: str
    pincode: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExternalOrder:
    external_source: str
    external_order_id: Optional[str] = None
    external_order_status: str = "not_integrated"  # "not_integrated", "handoff_provided", "submitted", "confirmed"
    external_checkout_url: Optional[str] = None
    integration_type: str = "handoff_link"  # "handoff_link" vs "official_api"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class OrderRecord:
    medscript_order_id: str
    items: List[Dict[str, Any]]
    shipping_address: Dict[str, Any]
    subtotal: float
    delivery_fee: float
    tax_amount: float
    total_amount: float
    payment_method: str
    payment_status: str  # "pending_on_delivery", "authorized", "paid", "failed"
    fulfillment_status: str  # "created", "processing", "submitted_to_pharmacy", "pharmacy_confirmed", "shipped", "delivered"
    requires_prescription: bool = False
    prescription_id: Optional[str] = None
    prescription_file_url: Optional[str] = None
    external_order: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC"))
    estimated_delivery: str = field(default_factory=lambda: "2 - 4 Business Days")
    user_id: Optional[str] = None
    user_email: Optional[str] = None

    @property
    def order_id(self) -> str:
        return self.medscript_order_id

    @property
    def order_status(self) -> str:
        return self.fulfillment_status

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["order_id"] = self.medscript_order_id
        d["order_status"] = self.fulfillment_status
        return d

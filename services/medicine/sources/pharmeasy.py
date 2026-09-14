"""
PharmEasy Medicine Source Adapter
Queries PharmEasy public search endpoint for Indian retail medicines, exact INR prices, and live stock.
Supports live product revalidation before checkout and direct retail purchase links.
"""
import sys
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import MedicineSource
from ..validators import is_prescription_required

logger = logging.getLogger("medscript.medicine.sources.pharmeasy")

class PharmEasySource(MedicineSource):
    SEARCH_URL = "https://pharmeasy.in/api/search/search/"

    def __init__(self, timeout: int = 8, enabled: bool = True):
        super().__init__(name="PharmEasy", timeout=timeout, enabled=enabled)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_raw(self, query: str, page: int = 1) -> Dict[str, Any]:
        params = {
            "q": query,
            "page": page
        }
        try:
            resp = requests.get(self.SEARCH_URL, headers=self.headers, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            return {"success": False, "items": [], "error": f"Network Error: {str(e)}"}

        if resp.status_code == 404:
            return {"success": True, "items": [], "error": None}

        if resp.status_code != 200:
            logger.warning(f"PharmEasy returned HTTP {resp.status_code}")
            return {"success": False, "items": [], "error": f"HTTP {resp.status_code}"}

        try:
            data = resp.json()
        except ValueError:
            return {"success": False, "items": [], "error": "Malformed JSON response"}

        products = data.get("data", {}).get("products", [])
        raw_items = []
        q_tokens = [t.lower() for t in query.split() if len(t) >= 2]

        for p in products:
            name = p.get("name")
            if not name:
                continue

            # Check prices
            sale_price = p.get("salePriceDecimal") or p.get("assuredDiscountPrice")
            mrp = p.get("mrpDecimal")
            if sale_price is None and mrp is None:
                # Skip non-medicine test packages or items without pricing
                continue

            try:
                sale_price = float(sale_price) if sale_price is not None else float(mrp)
            except (ValueError, TypeError):
                sale_price = None

            try:
                mrp = float(mrp) if mrp is not None else sale_price
            except (ValueError, TypeError):
                mrp = sale_price

            if sale_price is None or sale_price <= 0:
                continue

            # Discount percent
            discount_pct = p.get("discountPercent")
            if discount_pct is not None:
                try:
                    discount_pct = float(discount_pct)
                except (ValueError, TypeError):
                    discount_pct = None

            if (discount_pct is None or discount_pct <= 0) and mrp and sale_price and mrp > sale_price:
                discount_pct = round(((mrp - sale_price) / mrp) * 100, 1)

            # Metadata
            slug = (p.get("slug") or "").strip()
            molecule = (p.get("moleculeName") or "").strip()
            compositions_list = p.get("compositions") or []
            comp_names = [c.get("name") for c in compositions_list if isinstance(c, dict) and c.get("name")]
            comp_str = ", ".join(comp_names) if comp_names else None

            # Relevance guard: match against name, slug, molecule, or composition
            searchable_blob = f"{name.lower()} {slug.lower()} {molecule.lower()} {comp_str.lower() if comp_str else ''}"
            if q_tokens and not any(t in searchable_blob for t in q_tokens):
                continue

            prod_id = slug or str(p.get("productId") or name)
            product_url = f"https://pharmeasy.in/online-medicine-order/{slug}" if slug else "https://pharmeasy.in"

            # Image
            img_url = p.get("image")
            if not img_url:
                dam_images = p.get("damImages") or []
                if isinstance(dam_images, list) and len(dam_images) > 0 and isinstance(dam_images[0], dict):
                    img_url = dam_images[0].get("url")

            # Availability
            avail_flags = p.get("productAvailabilityFlags") or {}
            is_avail = avail_flags.get("isAvailable")
            if is_avail is False:
                availability = "Out of Stock"
            else:
                availability = "In Stock"

            # Pack size & Manufacturer
            pack_size = p.get("subtitleText") or p.get("packSize") or p.get("packaging")
            manufacturer = p.get("manufacturer")
            form = p.get("productForm")

            rx_req = is_prescription_required(name=name, composition=comp_str, dosage_form=form)

            raw_items.append({
                "id": f"pharmeasy_{prod_id}",
                "source": "PharmEasy",
                "source_product_id": prod_id,
                "name": name,
                "brand_name": name,
                "generic_name": molecule if molecule else None,
                "composition": comp_str,
                "dosage_form": form,
                "manufacturer": manufacturer,
                "pack_size": pack_size,
                "price": sale_price,
                "mrp": mrp,
                "discount": discount_pct,
                "discount_percent": discount_pct,
                "currency": "INR",
                "availability": availability,
                "stock_status": availability,
                "prescription_required": rx_req,
                "product_type": "ALLOPATHY",
                "url": product_url,
                "source_url": product_url,
                "image_url": img_url
            })

        return {"success": True, "items": raw_items, "error": None}

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        clean_id = str(product_id).replace("pharmeasy_", "").strip()
        res = self.search(clean_id)
        if res.get("success") and res.get("items"):
            for item in res["items"]:
                if clean_id in str(item.get("source_product_id", "")) or clean_id in str(item.get("source_url", "")):
                    return item
            return res["items"][0]
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    q = sys.argv[1] if len(sys.argv) > 1 else "paracetamol"
    source = PharmEasySource()
    res = source.search(q)
    print(f"PharmEasy search for '{q}': success={res['success']}, items={len(res['items'])}")
    for r in res['items'][:5]:
        print(f"- {r['name']} | Rs. {r['price']} | MRP: Rs. {r['mrp']} | Disc: {r['discount']}% | Rx: {r['prescription_required']} | {r['availability']} | URL: {r['source_url']}")

"""
OpenFDA NDC Directory Source Adapter
Official FDA drug database for clinical active ingredients, strengths, forms, and Rx/OTC status.
Explicitly treats HTTP 404 (zero catalog matches) as success with empty list.
"""
import sys
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import MedicineSource
from ..validators import is_prescription_required

logger = logging.getLogger("medscript.medicine.sources.openfda")

class OpenFDASource(MedicineSource):
    SEARCH_URL = "https://api.fda.gov/drug/ndc.json"

    def __init__(self, timeout: int = 8, enabled: bool = True):
        super().__init__(name="OpenFDA", timeout=timeout, enabled=enabled)
        self.headers = {
            "User-Agent": "MedScript-ClinicalSearch/1.0",
            "Accept": "application/json"
        }

    def fetch_raw(self, query: str, page: int = 1) -> Dict[str, Any]:
        search_query = f'brand_name:"{query}" generic_name:"{query}"'
        params = {
            "search": search_query,
            "limit": 10
        }
        try:
            resp = requests.get(self.SEARCH_URL, headers=self.headers, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            return {"success": False, "items": [], "error": f"Network Error: {str(e)}"}

        if resp.status_code == 404:
            # FDA API returns 404 when search query has 0 matches. This is NOT a system error.
            return {"success": True, "items": [], "error": None}

        if resp.status_code != 200:
            logger.info(f"OpenFDA search returned status {resp.status_code} for '{query}'")
            return {"success": False, "items": [], "error": f"HTTP {resp.status_code}"}

        try:
            data = resp.json()
        except ValueError:
            return {"success": False, "items": [], "error": "Malformed JSON response"}

        results = data.get("results", [])
        raw_items = []

        for item in results:
            brand_name = item.get("brand_name")
            generic_name = item.get("generic_name")
            name = brand_name or generic_name
            if not name:
                continue

            # Extract active ingredients & strength
            ingredients = item.get("active_ingredients", [])
            strength_str = None
            comp_str = None
            if ingredients and isinstance(ingredients, list):
                parts = [f"{ing.get('name', '')} {ing.get('strength', '')}".strip() for ing in ingredients if ing.get('name')]
                strength_str = ", ".join(parts) if parts else None
                comp_str = "; ".join(parts) if parts else None

            # Packaging
            packaging = item.get("packaging", [])
            pack_desc = packaging[0].get("description") if packaging else None

            ndc = item.get("product_ndc") or item.get("id") or name
            fda_url = f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={query}"

            # Prescription requirement from FDA route/marketing category
            mkt_cat = str(item.get("marketing_category", "")).upper()
            form = item.get("dosage_form")
            rx_from_source = "PRESCRIPTION" in mkt_cat or "NDA" in mkt_cat or "ANDA" in mkt_cat
            rx_req = is_prescription_required(name=name, composition=comp_str, dosage_form=form, source_flag=rx_from_source)

            raw_items.append({
                "id": f"fda_{ndc}",
                "source": "OpenFDA Clinical",
                "source_product_id": str(ndc),
                "name": name,
                "brand_name": brand_name,
                "generic_name": generic_name,
                "strength": strength_str,
                "composition": comp_str,
                "dosage_form": form,
                "manufacturer": item.get("labeler_name"),
                "pack_size": pack_desc,
                "price": None,
                "mrp": None,
                "discount": None,
                "currency": "INR",
                "availability": "In Stock",
                "stock_status": "In Stock",
                "prescription_required": rx_req,
                "product_type": "REGULATORY_RECORD",
                "url": fda_url,
                "source_url": fda_url,
                "image_url": None
            })

        return {"success": True, "items": raw_items, "error": None}

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        clean_id = str(product_id).replace("fda_", "").strip()
        params = {"search": f'product_ndc:"{clean_id}"', "limit": 1}
        try:
            resp = requests.get(self.SEARCH_URL, headers=self.headers, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    raw_res = self.fetch_raw(clean_id)
                    if raw_res.get("items"):
                        return raw_res["items"][0]
        except Exception:
            pass
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    q = sys.argv[1] if len(sys.argv) > 1 else "amoxicillin"
    source = OpenFDASource()
    res = source.search(q)
    print(f"OpenFDA search for '{q}': success={res['success']}, items={len(res['items'])}")
    for r in res['items'][:5]:
        print(f"- {r['name']} | Form: {r['dosage_form']} | Rx: {r['prescription_required']}")

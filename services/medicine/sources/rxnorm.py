"""
RxNorm Medicine Source Adapter
Queries National Library of Medicine (NLM) RxNav API for clinical drug concepts and standardized formulations.
"""
import sys
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import MedicineSource
from ..validators import is_prescription_required

logger = logging.getLogger("medscript.medicine.sources.rxnorm")

class RxNormSource(MedicineSource):
    SEARCH_URL = "https://rxnav.nlm.nih.gov/REST/drugs.json"
    RXCUI_URL = "https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json"

    def __init__(self, timeout: int = 8, enabled: bool = True):
        super().__init__(name="RxNorm", timeout=timeout, enabled=enabled)
        self.headers = {
            "Accept": "application/json"
        }

    def fetch_raw(self, query: str, page: int = 1) -> Dict[str, Any]:
        params = {"name": query}
        try:
            resp = requests.get(self.SEARCH_URL, headers=self.headers, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            return {"success": False, "items": [], "error": f"Network Error: {str(e)}"}

        if resp.status_code == 404:
            return {"success": True, "items": [], "error": None}

        if resp.status_code != 200:
            logger.info(f"RxNorm status {resp.status_code} for '{query}'")
            return {"success": False, "items": [], "error": f"HTTP {resp.status_code}"}

        try:
            data = resp.json()
        except ValueError:
            return {"success": False, "items": [], "error": "Malformed JSON response"}

        drug_group = data.get("drugGroup", {})
        concept_group = drug_group.get("conceptGroup", [])

        raw_items = []
        for group in concept_group:
            tty = group.get("tty")  # e.g., SBD (Semantic Branded Drug), SCD (Semantic Clinical Drug)
            concepts = group.get("conceptProperties", [])
            for c in concepts[:6]:
                name = c.get("name")
                rxcui = c.get("rxcui")
                if not name:
                    continue

                rxnav_url = f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}"
                rx_req = is_prescription_required(name=name, composition=None, dosage_form=None)

                raw_items.append({
                    "id": f"rx_{rxcui}",
                    "source": "RxNorm NLM",
                    "source_product_id": str(rxcui),
                    "name": name,
                    "brand_name": name if tty in ["SBD", "BN"] else None,
                    "generic_name": name if tty in ["SCD", "IN", "PIN"] else None,
                    "composition": None,
                    "dosage_form": None,  # Will be extracted by normalizer
                    "manufacturer": "Clinical Reference",
                    "pack_size": None,
                    "price": None,
                    "mrp": None,
                    "discount": None,
                    "currency": "INR",
                    "availability": "In Stock",
                    "stock_status": "In Stock",
                    "prescription_required": rx_req,
                    "product_type": "CLINICAL_CONCEPT",
                    "url": rxnav_url,
                    "source_url": rxnav_url,
                    "image_url": None
                })

        return {"success": True, "items": raw_items, "error": None}

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        clean_rxcui = str(product_id).replace("rx_", "").strip()
        url = self.RXCUI_URL.format(rxcui=clean_rxcui)
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                prop = resp.json().get("properties", {})
                name = prop.get("name")
                if name:
                    return {
                        "id": f"rx_{clean_rxcui}",
                        "source": "RxNorm NLM",
                        "source_product_id": clean_rxcui,
                        "name": name,
                        "price": None,
                        "availability": "In Stock",
                        "prescription_required": is_prescription_required(name=name)
                    }
        except Exception:
            pass
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    q = sys.argv[1] if len(sys.argv) > 1 else "ibuprofen"
    source = RxNormSource()
    res = source.search(q)
    print(f"RxNorm search for '{q}': success={res['success']}, items={len(res['items'])}")
    for r in res['items'][:5]:
        print(f"- {r['name']} | ID: {r['id']} | Rx: {r['prescription_required']}")

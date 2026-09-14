"""
MedScript Medicine Search Engine
Orchestrates multi-source concurrent querying, caching, normalization,
deduplication, price comparison, multi-factor ranking, and single-product revalidation.
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .models import NormalizedMedicine, SearchResult
from .normalizer import normalize_medicine_record
from .deduplicator import deduplicate_and_compare
from .cache import medicine_cache
from .sources.base import MedicineSource
from .sources.pharmeasy import PharmEasySource
from .sources.openfda import OpenFDASource
from .sources.rxnorm import RxNormSource

logger = logging.getLogger("medscript.medicine.search")

class MedicineSearchEngine:
    def __init__(self, sources: Optional[List[MedicineSource]] = None, max_workers: int = 4, timeout: int = 8):
        self.sources = sources or [
            PharmEasySource(timeout=timeout),
            OpenFDASource(timeout=timeout),
            RxNormSource(timeout=timeout)
        ]
        self.max_workers = max_workers
        self.timeout = timeout

    def search(self, query: str, page: int = 1, force_refresh: bool = False) -> SearchResult:
        clean_query = query.strip()
        if not clean_query:
            return SearchResult(
                query="",
                total=0,
                results=[],
                sources={s.name: {"success": True, "count": 0, "error": None} for s in self.sources}
            )

        start_time = time.time()

        # Check Cache
        if not force_refresh:
            cached_entry = medicine_cache.get(clean_query)
            if cached_entry:
                cached_res, cached_ts = cached_entry
                elapsed_str = medicine_cache.format_elapsed(cached_ts)
                res_items = [NormalizedMedicine.from_dict(item) if isinstance(item, dict) else item for item in cached_res]

                logger.info(f"Cache HIT for query='{clean_query}' ({len(res_items)} items, {elapsed_str})")
                return SearchResult(
                    query=clean_query,
                    total=len(res_items),
                    results=res_items,
                    sources={s.name: {"success": True, "count": len([m for m in res_items if m.source == s.name or s.name in m.source]), "error": None} for s in self.sources},
                    cached=True,
                    cached_at=elapsed_str,
                    elapsed_seconds=time.time() - start_time
                )

        # Multi-source concurrent execution
        sources_status: Dict[str, Dict[str, Any]] = {}
        raw_accumulated = []

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.sources))) as executor:
            future_to_source = {
                executor.submit(source.search, clean_query, page=page): source
                for source in self.sources
            }

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    res_dict = future.result(timeout=self.timeout + 1)
                    success = res_dict.get("success", False)
                    items = res_dict.get("items", [])
                    err = res_dict.get("error")

                    sources_status[source.name] = {
                        "success": success,
                        "count": len(items),
                        "error": err
                    }
                    if items:
                        raw_accumulated.extend(items)
                except Exception as e:
                    logger.error(f"Source [{source.name}] thread exception: {str(e)}")
                    sources_status[source.name] = {
                        "success": False,
                        "count": 0,
                        "error": f"{type(e).__name__}: {str(e)}"
                    }

        # Normalization and Validation
        normalized_medicines: List[NormalizedMedicine] = []
        rejected_count = 0

        for raw in raw_accumulated:
            norm_dict = normalize_medicine_record(raw, source_default=raw.get("source", "Unknown"))
            if norm_dict:
                normalized_medicines.append(NormalizedMedicine.from_dict(norm_dict))
            else:
                rejected_count += 1

        logger.info(f"Normalized {len(normalized_medicines)} medicines, rejected {rejected_count} invalid records")

        # Deduplication and Price Comparison
        processed_medicines = deduplicate_and_compare(normalized_medicines)

        # Multi-Factor Relevance Ranking
        q_lower = clean_query.lower()
        q_tokens = [t for t in q_lower.split() if len(t) > 1]

        def rank_score(med: NormalizedMedicine) -> Tuple[int, int, int, int, int, float]:
            name_lower = med.name.lower()
            generic_lower = (med.generic_name or "").lower()
            brand_lower = (med.brand_name or "").lower()

            # 1. Top Priority: Verified retail price and direct store purchase link
            has_retail_price = 0 if (med.price is not None and med.price > 0 and med.source_url) else 1
            # 2. Exact name or brand match
            exact_match = 0 if name_lower == q_lower or brand_lower == q_lower or generic_lower == q_lower else 1
            # 3. Query starts with name or brand
            starts_with = 0 if name_lower.startswith(q_lower) or brand_lower.startswith(q_lower) else 1
            # 4. Generic active ingredient match
            generic_match = 0 if any(t in generic_lower for t in q_tokens) else 1
            # 5. In Stock priority
            stock_priority = 0 if med.availability == "In Stock" else 1

            return (has_retail_price, exact_match, starts_with, generic_match, stock_priority, med.price or 999999)

        processed_medicines.sort(key=rank_score)

        # Save to Cache
        medicine_cache.set(clean_query, [m.to_dict() for m in processed_medicines])

        duration = time.time() - start_time
        return SearchResult(
            query=clean_query,
            total=len(processed_medicines),
            results=processed_medicines,
            sources=sources_status,
            cached=False,
            cached_at="Just now",
            elapsed_seconds=duration,
            last_updated=datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")
        )

    def get_live_product(self, source_name: str, product_id: str) -> Optional[NormalizedMedicine]:
        """
        Queries the specific live source to revalidate a product's price and stock before checkout.
        """
        target_source = None
        for s in self.sources:
            if s.name.lower() == source_name.lower():
                target_source = s
                break

        if not target_source:
            # Try PharmEasy by default for retail products
            target_source = self.sources[0]

        try:
            raw_product = target_source.get_product(product_id)
            if raw_product:
                norm_dict = normalize_medicine_record(raw_product, source_default=target_source.name)
                if norm_dict:
                    return NormalizedMedicine.from_dict(norm_dict)
        except Exception as e:
            logger.error(f"Live product lookup error on [{source_name}] for ID '{product_id}': {str(e)}")

        return None

    def suggest(self, query: str, limit: int = 6) -> List[Dict[str, Any]]:
        clean = query.strip()
        if len(clean) < 2:
            return []

        search_res = self.search(clean)
        suggestions = []
        seen = set()

        for med in search_res.results:
            name_core = med.name.strip()
            if name_core.lower() not in seen:
                seen.add(name_core.lower())
                suggestions.append({
                    "name": name_core,
                    "strength": med.strength or "",
                    "dosage_form": med.dosage_form or "",
                    "manufacturer": med.manufacturer or "",
                    "price": med.price,
                    "prescription_required": med.prescription_required
                })
                if len(suggestions) >= limit:
                    break

        return suggestions

# Default engine instance
medicine_engine = MedicineSearchEngine()

"""
MedScript Deduplication & Price Comparison Engine
Merges equivalent medicines across DIFFERENT sources, groups alternative offers,
and highlights the lowest verified price without cannibalizing distinct brands or same-source products.
"""
import re
from typing import List, Dict, Any
from .models import NormalizedMedicine

def make_dedup_key(med: NormalizedMedicine) -> str:
    """
    Builds a conservative equivalence key.
    Merges identical brands across DIFFERENT sources,
    but keeps different brands and same-source products distinct.
    """
    brand_or_name = (med.brand_name or med.name or "").lower().strip()
    brand_or_name = re.sub(r"[^\w\s]", " ", brand_or_name)
    name_tokens = [
        t for t in brand_or_name.split()
        if t not in ["tablets", "tablet", "capsules", "capsule", "mg", "ml", "strip", "of", "pack", "bottle", "suspension", "er", "sr", "dt", "ip", "bp", "usp"]
    ]
    clean_brand = " ".join(name_tokens[:2]) if name_tokens else "med"

    strength = (med.strength or "").lower().replace(" ", "").strip()
    dosage_form = (med.dosage_form or "").lower().strip()

    if not strength and not dosage_form:
        return f"unmerged_{med.source}_{med.id}"

    return f"{clean_brand}_{strength}_{dosage_form}"

def deduplicate_and_compare(medicines: List[NormalizedMedicine]) -> List[NormalizedMedicine]:
    """
    Groups identical medicines across different platforms.
    Ensures that products from the same source are never collapsed into each other.
    """
    if not medicines:
        return []

    clusters: Dict[str, List[NormalizedMedicine]] = {}
    for med in medicines:
        key = make_dedup_key(med)
        if key not in clusters:
            clusters[key] = []

        existing_sources = {m.source for m in clusters[key]}
        if med.source in existing_sources:
            # Different product or pack size from the same source: keep distinct
            clusters[f"{key}_{med.id}"] = [med]
        else:
            clusters[key].append(med)

    deduplicated_list: List[NormalizedMedicine] = []

    for key, group in clusters.items():
        if len(group) == 1:
            deduplicated_list.append(group[0])
            continue

        valid_prices = [m for m in group if m.price is not None and m.price > 0]
        min_price = min([m.price for m in valid_prices]) if valid_prices else None

        # Choose primary record: prefer verified retail price, then In Stock
        group_sorted = sorted(
            group,
            key=lambda m: (
                0 if m.price is not None and m.price > 0 else 1,
                0 if m.availability == "In Stock" else 1,
                m.price if m.price is not None else 999999
            )
        )
        primary = group_sorted[0]

        other_offers = []
        sources_seen = {primary.source}
        for item in group_sorted[1:]:
            offer = {
                "source": item.source,
                "price": item.price,
                "currency": item.currency,
                "mrp": item.mrp,
                "availability": item.availability,
                "source_url": item.source_url,
                "is_lowest": (item.price == min_price) if (item.price and min_price) else False
            }
            other_offers.append(offer)
            sources_seen.add(item.source)

        primary.equivalent_sources_count = len(sources_seen)
        primary.other_sources = other_offers
        if min_price and primary.price == min_price and len(sources_seen) > 1:
            primary.is_lowest_price = True

        deduplicated_list.append(primary)

    return deduplicated_list

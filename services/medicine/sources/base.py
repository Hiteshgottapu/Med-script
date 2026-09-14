"""
MedScript Base Medicine Source Adapter
Standardized interface for all medicine data providers with error isolation,
clean distinction between 404/empty and technical failure, rate limiting, and single-product revalidation.
"""
from abc import ABC, abstractmethod
import logging
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("medscript.medicine.sources")

class MedicineSource(ABC):
    """
    Common abstract interface for all medicine data providers.
    Every source implements search and live product revalidation.
    """
    def __init__(self, name: str, timeout: int = 8, enabled: bool = True):
        self.name = name
        self.timeout = timeout
        self.enabled = enabled
        self._last_request_time = 0.0
        self._min_interval = 0.2  # 200ms throttle between requests to same source

    def _throttle(self):
        """Enforces a gentle rate-limit delay between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @abstractmethod
    def fetch_raw(self, query: str, page: int = 1) -> Dict[str, Any]:
        """
        Subclasses must implement actual HTTP or API retrieval.
        Must return a dict: {"success": bool, "items": list, "error": Optional[str]}
        """
        pass

    @abstractmethod
    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves current live product record for price/stock revalidation.
        """
        pass

    def search(self, query: str, page: int = 1) -> Dict[str, Any]:
        """
        Public entrypoint with safety wrapper, timing, error capture, and logging.
        Never raises exceptions to callers; logs and returns structured result.
        """
        if not self.enabled:
            logger.info(f"Source [{self.name}] is disabled, skipping.")
            return {
                "source": self.name,
                "success": False,
                "items": [],
                "error": "Source is currently disabled"
            }

        clean_query = query.strip()
        if not clean_query:
            return {
                "source": self.name,
                "success": True,
                "items": [],
                "error": None
            }

        start_time = time.time()
        try:
            self._throttle()
            res = self.fetch_raw(clean_query, page=page)
            duration_ms = round((time.time() - start_time) * 1000, 1)
            
            items = res.get("items", [])
            success = res.get("success", True)
            error = res.get("error")

            logger.info(f"Source [{self.name}] query='{clean_query}' success={success} items={len(items)} in {duration_ms}ms")
            return {
                "source": self.name,
                "success": success,
                "items": items,
                "error": error,
                "duration_ms": duration_ms
            }
        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 1)
            logger.error(f"Source [{self.name}] query='{clean_query}' EXCEPTION in {duration_ms}ms: {str(e)}")
            return {
                "source": self.name,
                "success": False,
                "items": [],
                "error": f"{type(e).__name__}: {str(e)}",
                "duration_ms": duration_ms
            }

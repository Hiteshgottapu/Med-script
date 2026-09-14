"""
MedScript Medicine Search Cache
Thread-safe in-memory cache with configurable TTL and timestamp helpers.
"""
import time
import threading
from typing import Optional, Any, Tuple
from datetime import datetime

class MedicineCache:
    def __init__(self, default_ttl_seconds: int = 900):  # 15 minutes TTL
        self.default_ttl = default_ttl_seconds
        self._cache = {}
        self._lock = threading.Lock()

    def _normalize_key(self, query: str) -> str:
        return " ".join(query.lower().strip().split())

    def get(self, query: str) -> Optional[Tuple[Any, float]]:
        """
        Returns (cached_data, timestamp_created) if present and not expired.
        Otherwise returns None.
        """
        key = self._normalize_key(query)
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            data, timestamp, ttl = entry
            if time.time() - timestamp > ttl:
                # Expired
                del self._cache[key]
                return None
            return data, timestamp

    def set(self, query: str, data: Any, ttl_seconds: Optional[int] = None):
        """Stores data with timestamp and TTL."""
        key = self._normalize_key(query)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        with self._lock:
            self._cache[key] = (data, time.time(), ttl)

    def clear(self):
        """Clears all cached items."""
        with self._lock:
            self._cache.clear()

    @staticmethod
    def format_elapsed(timestamp: float) -> str:
        """Returns friendly human string e.g. 'Updated just now' or 'Updated 4 min ago'."""
        elapsed = max(0, time.time() - timestamp)
        if elapsed < 60:
            return "Updated just now"
        mins = int(elapsed // 60)
        if mins == 1:
            return "Updated 1 min ago"
        if mins < 60:
            return f"Updated {mins} min ago"
        hrs = int(mins // 60)
        return f"Updated {hrs} hr ago"

# Global singleton instance
medicine_cache = MedicineCache()

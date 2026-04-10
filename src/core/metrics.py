import time
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
class PerformanceMetrics:
    """In-memory performance metrics collector"""
    def __init__(self):
        self.query_times: list[float] = []  # in milliseconds
        self.confidence_scores: list[float] = []
        self.sources_used: dict[str, int] = {}  # source -> count
        self.query_count: int = 0
        self._lock = False  # Simple lock to prevent concurrent writes

    def record_query(self, response_time_ms: float, confidence: float, sources: list[str]):
        """Record a query execution"""
        import threading
        with threading.Lock():
            self.query_times.append(response_time_ms)
            if len(self.query_times) > 1000:  # Keep last 1000
                self.query_times = self.query_times[-1000:]
            self.confidence_scores.append(confidence)
            if len(self.confidence_scores) > 1000:
                self.confidence_scores = self.confidence_scores[-1000:]
            for src in sources:
                self.sources_used[src] = self.sources_used.get(src, 0) + 1
            self.query_count += 1

    def get_percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * percentile / 100)
        idx = min(idx, len(sorted_vals) - 1)
        return round(sorted_vals[idx], 2)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregated performance statistics"""
        if not self.query_times:
            return {
                "query_count": 0,
                "response_time_p50": 0,
                "response_time_p95": 0,
                "response_time_p99": 0,
                "avg_confidence": 0,
                "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
                "source_coverage": {"CAAC": 0, "FAA": 0, "EASA": 0, "OTHER": 0},
                "top_sources": [],
                "top_queries": []
            }

        import threading
        with threading.Lock():
            times = list(self.query_times)
            confidences = list(self.confidence_scores)
            sources = dict(self.sources_used)
            count = self.query_count

        # Calculate confidence distribution
        high = sum(1 for c in confidences if c >= 0.7)
        medium = sum(1 for c in confidences if 0.4 <= c < 0.7)
        low = sum(1 for c in confidences if c < 0.4)
        total = len(confidences) or 1

        # Source coverage by agency
        agency_sources = {"CAAC": 0, "FAA": 0, "EASA": 0, "OTHER": 0}
        for src, cnt in sources.items():
            src_upper = src.upper()
            if "CCAR" in src_upper or "CAAC" in src_upper:
                agency_sources["CAAC"] += cnt
            elif "FAR" in src_upper or "FAA" in src_upper:
                agency_sources["FAA"] += cnt
            elif "CS-" in src_upper or "EASA" in src_upper:
                agency_sources["EASA"] += cnt
            else:
                agency_sources["OTHER"] += cnt

        # Top sources by count
        top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]

        # Response time stats
        p50 = self.get_percentile(times, 50)
        p95 = self.get_percentile(times, 95)
        p99 = self.get_percentile(times, 99)

        return {
            "query_count": count,
            "response_time_p50": p50,
            "response_time_p95": p95,
            "response_time_p99": p99,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "confidence_distribution": {
                "high": round(high / total * 100, 1),
                "medium": round(medium / total * 100, 1),
                "low": round(low / total * 100, 1)
            },
            "source_coverage": agency_sources,
            "top_sources": [{"source": s, "count": c} for s, c in top_sources],
            "top_queries": []  # Placeholder for future query logging
        }


metrics_collector = PerformanceMetrics()




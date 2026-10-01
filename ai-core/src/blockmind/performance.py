"""Aggregate timings, not per-tick logs. Timings may overlap across layers."""
from collections import Counter
from contextlib import contextmanager
from time import perf_counter


class PerformanceMetrics:
    def __init__(self):
        self.started = perf_counter()
        self.seconds = Counter()
        self.counts = Counter()

    @contextmanager
    def measure(self, name):
        start = perf_counter()
        try:
            yield
        finally:
            self.seconds[name] += perf_counter() - start
            self.counts[name] += 1

    def snapshot(self):
        elapsed = perf_counter() - self.started
        return {"elapsed": elapsed, "blocks_placed": self.counts["blocks_placed"],
                "blocks_per_second": self.counts["blocks_placed"] / elapsed if elapsed else 0,
                "operations_per_second": self.counts["operation_attempts"] / elapsed if elapsed else 0,
                "mean_seconds": {key: value / self.counts[key] for key, value in self.seconds.items() if self.counts[key]},
                "seconds": dict(self.seconds), "counts": dict(self.counts)}

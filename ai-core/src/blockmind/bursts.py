"""Bounded local cube runs; feedback always comes from observed block states."""
from dataclasses import dataclass

from .execution import OperationClass, classify
from .models import Bounds, BuildOperation, Vec3i
from .scheduler import zone_id


@dataclass(frozen=True)
class BuildBurst:
    operations: tuple[BuildOperation, ...]
    feet: Vec3i
    zone: str
    approved_area: Bounds
    verified_dependencies: frozenset[str] = frozenset()

    def __post_init__(self):
        if not 1 <= len(self.operations) <= 32:
            raise ValueError("burst must contain 1..32 operations")
        if len({op.id for op in self.operations}) != len(self.operations):
            raise ValueError("duplicate burst operation")
        if len({op.block for op in self.operations}) != 1:
            raise ValueError("burst requires one material")
        batch_ids = {op.id for op in self.operations}
        if any(classify(op) != OperationClass.SIMPLE
               or any(dep not in self.verified_dependencies or dep in batch_ids for dep in op.depends_on)
               or zone_id(op) != self.zone or not self.approved_area.contains(op.position)
               for op in self.operations):
            raise ValueError("burst crosses a safety, dependency, or work-zone boundary")


class AdaptiveBurstController:
    """Conservative growth, immediate reduction on mismatch or expensive repair.

    An 'issued' acknowledgement is not verification. Call feedback only after a
    compact block-state validation. Truncated local runs do not prove that a
    larger run is reliable, and therefore cannot trigger growth.
    """
    def __init__(self, maximum: int):
        if not 1 <= maximum <= 32:
            raise ValueError("maximum must be 1..32")
        self.maximum = maximum
        self.size = min(8, maximum)
        self.clean_full_runs = 0
        self.issued = self.verified = self.mismatches = self.repairs = 0

    def feedback(self, *, attempted: int, issued: int, verified: int, repairs: int = 0):
        if not 0 <= issued <= attempted or not 0 <= verified <= attempted or repairs < 0:
            raise ValueError("invalid verified burst feedback")
        self.issued += issued
        self.verified += verified
        self.mismatches += attempted - verified
        self.repairs += repairs
        if verified != attempted or repairs:
            self.size = max(1, self.size // 2)
            self.clean_full_runs = 0
        elif attempted >= self.size:
            self.clean_full_runs += 1
            if self.clean_full_runs >= 2:
                self.size = min(self.maximum, self.size + 2)
                self.clean_full_runs = 0

    def snapshot(self):
        total = self.verified + self.mismatches
        return {"size": self.size, "maximum": self.maximum, "issued": self.issued,
                "verified": self.verified, "mismatches": self.mismatches,
                "mismatch_rate": self.mismatches / total if total else 0.0,
                "repair_operations": self.repairs}

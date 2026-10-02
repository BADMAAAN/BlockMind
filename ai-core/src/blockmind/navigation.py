from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from .models import Vec3i, WorldState


class NavigationGoalKind(str, Enum):
    GO_TO = "go_to"
    APPROACH = "approach"
    MOVE_TO_BUILD_POSITION = "move_to_build_position"
    FOLLOW = "follow"
    EXPLORE = "explore"
    RETURN_TO = "return_to"


@dataclass(frozen=True)
class NavigationGoal:
    kind: NavigationGoalKind
    target: Vec3i
    tolerance: float = 2.5
    avoid_hazards: bool = True


@dataclass(frozen=True)
class NavigationResult:
    success: bool
    position: Vec3i
    reason: str = ""
    used_alternative: bool = False


def failure_kind(reason: str) -> str:
    reason = reason.lower()
    for needle, kind in (("unloaded", "unloaded_region"), ("drop", "unsafe_drop"), ("stale", "stale_route"),
                         ("blocked", "blocked_path"), ("displaced", "player_displaced"), ("scaffold", "missing_access"),
                         ("unreachable", "unreachable_position"), ("stopped before", "unreachable_position"),
                         ("paused", "control_interrupt"), ("cancel", "control_interrupt")):
        if needle in reason: return kind
    return "provider_failure"


class NavigationProvider(ABC):
    @abstractmethod
    async def navigate(self, goal: NavigationGoal, world: WorldState) -> NavigationResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self) -> None:
        raise NotImplementedError


class SafeSimulatedNavigationProvider(NavigationProvider):
    """Deterministic test provider that demonstrates hazard rejection and rerouting."""

    def __init__(self) -> None:
        self.cancelled = False

    async def navigate(self, goal: NavigationGoal, world: WorldState) -> NavigationResult:
        # Cancellation ends current work, not all future goals after an explicit resume.
        self.cancelled = False
        target = goal.target
        if goal.avoid_hazards and world.is_hazardous(target):
            alternatives = [target.offset(dx=dx, dz=dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (0, 2))]
            safe = next((candidate for candidate in alternatives if not world.is_hazardous(candidate)), None)
            if safe is None:
                return NavigationResult(False, world.player.position, "no safe approach position")
            world.player.position = safe
            return NavigationResult(True, safe, "unsafe direct position rejected", True)
        world.player.position = target
        return NavigationResult(True, target)

    async def cancel(self) -> None:
        self.cancelled = True

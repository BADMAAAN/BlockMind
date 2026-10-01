"""Execution policy and dependency-aware ordering; raw geometry remains unchanged."""
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
import tomllib
from .models import BuildOperation, OperationKind


class OperationClass(str, Enum):
    SIMPLE = "simple_placement"
    STATEFUL = "stateful_placement"
    CRITICAL = "critical_placement"
    DESTRUCTIVE = "destructive_operation"


def classify(op: BuildOperation) -> OperationClass:
    if op.kind != OperationKind.PLACE:
        return OperationClass.DESTRUCTIVE
    if op.temporary or op.verify_only or op.attempts or op.block == "minecraft:water":
        return OperationClass.CRITICAL
    if op.properties:
        return OperationClass.STATEFUL
    name = (op.block or "").removeprefix("minecraft:")
    cubes = {"stone", "cobblestone", "smooth_quartz", "quartz_block", "bricks", "dirt", "glass"}
    return OperationClass.SIMPLE if name in cubes or name.endswith(("_planks", "_concrete", "_wool")) else OperationClass.STATEFUL


@dataclass
class ExecutionConfig:
    speed_profile: str = "fast"
    adaptive_verification: bool = True
    component_validation: bool = True
    max_action_batch: int = 16
    placement_radius: float = 3.8
    reuse_interaction_positions: bool = True
    prefer_local_movement: bool = True
    mute_game_audio: bool = True
    restore_audio_after_build: bool = True

    def __post_init__(self):
        for name in ("adaptive_verification", "component_validation", "reuse_interaction_positions", "prefer_local_movement", "mute_game_audio", "restore_audio_after_build"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")
        if self.speed_profile not in ("safe", "normal", "fast", "max"):
            raise ValueError("unknown speed profile")
        if type(self.max_action_batch) is not int or isinstance(self.placement_radius, bool) or not isinstance(self.placement_radius, (int, float)):
            raise ValueError("batch must be an integer; placement radius must be numeric")
        if not 1 <= self.max_action_batch <= 32 or not 1 <= self.placement_radius <= 4.5:
            raise ValueError("batch must be 1..32; placement radius must be 1..4.5")

    @property
    def batch_size(self):
        return min(self.max_action_batch, {"safe": 1, "normal": 4, "fast": 16, "max": 32}[self.speed_profile])

    def to_dict(self):
        return asdict(self)

    @classmethod
    def load(cls, path: Path | None):
        if path is None or not path.exists():
            return cls()
        value = tomllib.loads(path.read_text(encoding="utf-8"))
        flat = {}
        allowed = set(cls.__dataclass_fields__)
        for section in ("execution", "navigation", "audio"):
            for key, item in value.get(section, {}).items():
                if key not in allowed:
                    raise ValueError(f"unknown configuration key: {section}.{key}")
                flat[key] = item
        return cls(**flat)


class BuildPlanOptimizer:
    def optimize(self, plan):
        """Stable component/layer serpentine sweeps, with stateful and dependency barriers.

        Only runs of simple operations in one layer are regrouped. Unknown/technical
        operations retain their original order; explicit dependencies are never crossed.
        """
        result, run = [], []
        def flush():
            if not run:
                return
            components = list(dict.fromkeys(op.component_id for op in run))
            for component in components:
                local = [op for op in run if op.component_id == component]
                result.extend(sorted(local, key=lambda op: (op.position.z,
                    op.position.x if op.position.z % 2 == 0 else -op.position.x, op.block or "")))
            run.clear()
        for op in plan.operations:
            if classify(op) != OperationClass.SIMPLE or op.depends_on:
                flush(); result.append(op)
            else:
                if run and run[-1].position.y != op.position.y:
                    flush()
                run.append(op)
        flush()
        seen = set()
        for op in result:
            if any(dep not in seen for dep in op.depends_on):
                raise ValueError("raw plan dependencies must precede their dependents")
            seen.add(op.id)
        return result

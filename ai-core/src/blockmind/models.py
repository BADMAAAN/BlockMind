from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, order=True)
class Vec3i:
    x: int
    y: int
    z: int

    def offset(self, dx: int = 0, dy: int = 0, dz: int = 0) -> "Vec3i":
        return Vec3i(self.x + dx, self.y + dy, self.z + dz)

    def distance_squared(self, other: "Vec3i") -> int:
        return (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class Bounds:
    minimum: Vec3i
    maximum: Vec3i

    def contains(self, point: Vec3i) -> bool:
        return all((self.minimum.x <= point.x <= self.maximum.x,
                    self.minimum.y <= point.y <= self.maximum.y,
                    self.minimum.z <= point.z <= self.maximum.z))

    def expanded(self, amount: int) -> "Bounds":
        return Bounds(self.minimum.offset(-amount, -amount, -amount),
                      self.maximum.offset(amount, amount, amount))

    def to_dict(self) -> dict[str, Any]:
        return {"minimum": self.minimum.to_dict(), "maximum": self.maximum.to_dict()}


class HazardKind(str, Enum):
    LAVA = "lava"
    FIRE = "fire"
    VOID = "void"
    DROWNING = "drowning"
    SUFFOCATION = "suffocation"
    UNSAFE_DROP = "unsafe_drop"
    HOT_SURFACE = "hot_surface"
    HOSTILE_ENTITY = "hostile_entity"


@dataclass(frozen=True)
class Hazard:
    kind: HazardKind
    bounds: Bounds
    severity: float
    detail: str = ""


@dataclass
class PlayerState:
    position: Vec3i
    dimension: str = "minecraft:overworld"
    health: float = 20.0
    hunger: int = 20
    creative: bool = True
    on_ground: bool = True
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    inventory: dict[str, int] = field(default_factory=dict)
    eye: tuple[float, float, float] | None = None


@dataclass
class WorldState:
    player: PlayerState
    blocks: dict[Vec3i, str] = field(default_factory=dict)
    hazards: list[Hazard] = field(default_factory=list)
    observed_bounds: Bounds | None = None
    properties: dict[Vec3i, dict[str, str]] = field(default_factory=dict)
    replaceable: set[Vec3i] = field(default_factory=set)
    solid: set[Vec3i] = field(default_factory=set)

    def block_at(self, position: Vec3i) -> str:
        return self.blocks.get(position, "minecraft:air")

    def is_hazardous(self, position: Vec3i, threshold: float = 0.5) -> bool:
        return any(h.severity >= threshold and h.bounds.contains(position) for h in self.hazards)


class OperationKind(str, Enum):
    PLACE = "place"
    BREAK = "break"
    INTERACT = "interact"


class OperationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StructureComponent:
    id: str
    kind: str
    bounds: Bounds
    material: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildOperation:
    kind: OperationKind
    position: Vec3i
    block: str | None
    component_id: str
    destructive: bool = False
    temporary: bool = False
    id: str = field(default_factory=lambda: str(uuid4()))
    status: OperationStatus = OperationStatus.PENDING
    attempts: int = 0
    error: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    verify_only: bool = False
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Design:
    name: str
    origin: Vec3i
    bounds: Bounds
    components: list[StructureComponent]
    parameters: dict[str, Any]


@dataclass
class BuildPlan:
    design: Design
    operations: list[BuildOperation]
    materials: dict[str, int]
    approved_area: Bounds
    temporary_area: Bounds | None = None


class ProjectStatus(str, Enum):
    DESIGNED = "designed"
    PLANNED = "planned"
    BUILDING = "building"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ProjectState:
    request: str
    design: Design
    plan: BuildPlan
    id: str = field(default_factory=lambda: str(uuid4()))
    status: ProjectStatus = ProjectStatus.PLANNED
    completed_operation_ids: list[str] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    modifications: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    temporary_blocks: list[dict[str, Any]] = field(default_factory=list)
    dimension: str | None = None
    baseline: list[dict[str, Any]] = field(default_factory=list)
    baseline_captured: bool = False
    execution: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if not self.plan.operations:
            return 1.0
        return len(self.completed_operation_ids) / len(self.plan.operations)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

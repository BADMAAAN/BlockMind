"""Deterministic global work-zone scheduling, separate from verification policy.

Stateful blocks are not route barriers. Dependencies, mutation barriers and house
construction phases are; raw geometry and operation identifiers never change.
"""
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from math import sqrt

from .models import Bounds, OperationKind, Vec3i


class Traversal(str, Enum):
    LINEAR = "linear"
    SERPENTINE = "serpentine"
    CLOCKWISE = "clockwise"
    COUNTER_CLOCKWISE = "counter_clockwise"
    LAYERED = "layered"
    COMPONENT_FIRST = "component_first"


@dataclass(frozen=True)
class WorkZone:
    id: str
    component: str
    subcomponent: str
    bounds: Bounds
    phase: int
    strategy: Traversal


def zone_id(op):
    # The two-block entrance belongs to the north facade, not a remote last pass.
    return "floor_1.wall_north" if op.component_id == "entrance" else op.component_id


def phase(op):
    name = zone_id(op)
    if name == "foundation": return 0
    if name.startswith("floor_") and "." in name:
        floor = int(name.split(".")[0].removeprefix("floor_"))
        return floor * 2 - (1 if name.endswith("slab") else 0)
    if name == "roof": return 100
    if name == "pool": return 101 if op.block != "minecraft:water" else 102
    return 0


def route_quality(operations):
    """Operation-target route proxy, NOT actual distance walked by the player."""
    switches = backtracks = elevation = materials = 0
    history = []
    distance = 0.0
    for previous, current in zip(operations, operations[1:]):
        distance += sqrt(previous.position.distance_squared(current.position))
        elevation += abs(previous.position.y-current.position.y)
        materials += previous.block != current.block
        if zone_id(previous) != zone_id(current):
            if not history: history.append(zone_id(previous))
            switches += 1
            backtracks += zone_id(current) in history[-4:]
            history.append(zone_id(current))
    return {"target_route_distance_blocks": distance, "region_switches": switches,
            "component_switches": switches, "backtracks": backtracks,
            "elevation_changes": elevation, "material_switches": materials}


class ConstructionScheduler:
    lookahead = 32

    def __init__(self):
        self.zones = {}
        self.decisions = []
        self.direction = None

    def optimize(self, plan, start=None, completed=(), active_zone=None, direction=None):
        self.metadata = {component.id: component.metadata for component in plan.design.components}
        for metadata in self.metadata.values():
            if "phase" in metadata and (type(metadata["phase"]) is not int or not 0 <= metadata["phase"] <= 10000):
                raise ValueError("component phase must be an integer in 0..10000")
            if metadata.get("support_order", "below") not in ("below", "above", "explicit"):
                raise ValueError("invalid component support order")
        operations = list(plan.operations)
        identifiers = {op.id for op in operations}
        if len(identifiers) != len(operations): raise ValueError("duplicate operation identifiers")
        if any(dep not in identifiers for op in operations for dep in op.depends_on):
            raise ValueError("unknown operation dependency")
        # Destructive/interaction work retains exact relative barriers; arbitrary
        # technical transformations cannot safely be reordered like placement.
        result, run = [], []
        cursor = start or plan.design.origin
        for op in operations:
            if op.kind != OperationKind.PLACE or op.temporary:
                ordered = self._schedule(run, cursor, set(completed), active_zone, direction, set(o.id for o in result))
                result.extend(ordered); run = []
                if ordered: cursor = ordered[-1].position
                if any(dep not in {o.id for o in result} for dep in op.depends_on):
                    raise ValueError("dependency crosses a mutation barrier")
                result.append(op); cursor = op.position
            else: run.append(op)
        result.extend(self._schedule(run, cursor, set(completed), active_zone, direction, set(o.id for o in result)))
        seen = set()
        for op in result:
            if any(dep not in seen for dep in op.depends_on): raise ValueError("cyclic execution dependencies")
            seen.add(op.id)
        return result

    def _schedule(self, operations, cursor, completed, active_zone, direction, prior):
        if not operations: return []
        groups = defaultdict(list)
        for op in operations: groups[(self.metadata.get(zone_id(op), {}).get("phase", phase(op)), zone_id(op))].append(op)
        perimeter = ["north", "east", "south", "west"]
        order = list(perimeter)
        faces = {name: [op for op in operations if zone_id(op).endswith("wall_"+name)] for name in perimeter}
        available = [name for name in perimeter if faces[name]]
        selected_direction = direction
        if available:
            first = min(available, key=lambda name: (min(cursor.distance_squared(o.position) for o in faces[name]), perimeter.index(name)))
            # Look one adjacent facade ahead; preserve the selected cycle thereafter.
            scores = {}
            for step, label in ((1, Traversal.CLOCKWISE), (-1, Traversal.COUNTER_CLOCKWISE)):
                cycle = [perimeter[(perimeter.index(first)+i*step)%4] for i in range(4)]
                present = [name for name in cycle if faces[name]]
                scores[label] = sum(min(a.position.distance_squared(b.position) for a in faces[left][:self.lookahead]
                    for b in faces[right][:self.lookahead]) for left,right in zip(present,present[1:]))
                axis = "x" if first in ("north", "south") else "z"
                reverse = first in ("south", "west")
                if step == -1: reverse = not reverse
                entry = min(faces[first], key=lambda op: (-getattr(op.position, axis) if reverse else getattr(op.position, axis), op.position.y))
                scores[label] += cursor.distance_squared(entry.position)
            selected_direction = selected_direction or min(scores, key=lambda k: (scores[k], k != Traversal.CLOCKWISE))
            step = 1 if selected_direction == Traversal.CLOCKWISE else -1
            order = [perimeter[(perimeter.index(first)+i*step)%4] for i in range(4)]
        self.direction = selected_direction.value if selected_direction else None
        pending = {}
        dependencies = {}
        by_position = {op.position: op for op in operations if not op.verify_only}
        for (number, name), items in groups.items():
            support_order = self.metadata.get(name, {}).get("support_order", "below")
            points = [op.position for op in items]
            bounds = Bounds(Vec3i(*(min(getattr(p, axis) for p in points) for axis in ("x","y","z"))),
                            Vec3i(*(max(getattr(p, axis) for p in points) for axis in ("x","y","z"))))
            if "wall_" in name: strategy = selected_direction or Traversal.LINEAR
            elif "window" in name: strategy = Traversal.COMPONENT_FIRST
            elif bounds.minimum.y != bounds.maximum.y: strategy = Traversal.LAYERED
            elif bounds.minimum.x != bounds.maximum.x and bounds.minimum.z != bounds.maximum.z: strategy = Traversal.SERPENTINE
            else: strategy = Traversal.LINEAR
            self.zones[name] = WorkZone(name, name.split(".")[0], name.split(".")[-1], bounds, number, strategy)
            def local_key(op):
                p = op.position
                if "wall_" in name:
                    side = name.split("wall_")[-1]
                    value = p.x if side in ("north", "south") else p.z
                    reverse = side in ("south", "west")
                    if selected_direction == Traversal.COUNTER_CLOCKWISE: reverse = not reverse
                    # Finish a vertical window/column before walking onward.
                    # The inferred below-cell edges still enforce support order.
                    return (-value if reverse else value, p.y, op.verify_only)
                if strategy == Traversal.LINEAR:
                    reverse = cursor.distance_squared(bounds.maximum) < cursor.distance_squared(bounds.minimum)
                    return (p.y, -p.z if reverse else p.z, -p.x if reverse else p.x, op.verify_only)
                return (-p.y if support_order == "above" else p.y, p.z, p.x if (p.z-bounds.minimum.z)%2 == 0 else -p.x, op.verify_only)
            pending[(number,name)] = sorted(items, key=local_key)
            for op in items:
                deps = set(op.depends_on)
                support = by_position.get(op.position.offset(dy=1 if support_order == "above" else -1)) if support_order != "explicit" else None
                if support and support.id != op.id: deps.add(support.id)
                dependencies[op.id] = deps
        emitted = set(prior)
        result = []
        recent = []
        current = active_zone
        while pending:
            ready_keys = [key for key, items in pending.items() if any(dependencies[op.id] <= emitted for op in items)]
            if not ready_keys: raise ValueError("cyclic or barrier-crossing construction dependency")
            earliest = min(key[0] for key in pending)
            allowed = [key for key in ready_keys if key[0] == earliest] or ready_keys
            def cost(key):
                number, name = key
                items = pending[key]
                ready = [op for op in items if dependencies[op.id] <= emitted][:self.lookahead]
                travel = sqrt(cursor.distance_squared(ready[0].position))
                finish_bias = -60 if name == current else 0
                fraction = sum(op.id in completed for op in items)/len(items)
                backtrack = 100 if name in recent[-4:] and name != current else 0
                # Perimeter cycle outweighs small material/distance savings.
                perimeter_rank = order.index(name.split("wall_")[-1])*40 if "wall_" in name else 0
                return (number, travel + finish_bias - 200*fraction + backtrack + perimeter_rank, name)
            selected = next((key for key in allowed if key[1] == current), None) or min(allowed, key=cost)
            name = selected[1]
            reason = "finish_active_zone" if name == current else "dependency_override" if selected[0] != earliest else "continuous_route"
            self.decisions.append({"zone": name, "strategy": self.zones[name].strategy.value, "reason": reason})
            if name != current:
                recent.append(name); current = name
            items = pending[selected]
            # Finish every dependency-ready operation in the chosen zone before switching.
            while True:
                op = next((op for op in items if dependencies[op.id] <= emitted), None)
                if op is None: break
                result.append(op); emitted.add(op.id); cursor = op.position; items.remove(op)
            if not items: del pending[selected]
        return result

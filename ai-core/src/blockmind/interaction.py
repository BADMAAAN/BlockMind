"""Deterministic interaction geometry, independent of game mapping names."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .models import BuildOperation, OperationKind, Vec3i, WorldState

AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def _clear_ray(world, eye, hit, target):
    """Bounded voxel traversal: fixed samples can jump across an occluding edge."""
    cell=[math.floor(v) for v in eye]
    delta=[hit[i]-eye[i] for i in range(3)]
    step=[1 if d>0 else -1 if d<0 else 0 for d in delta]
    crossing=[((cell[i]+(1 if step[i]>0 else 0)-eye[i])/delta[i]) if step[i] else math.inf for i in range(3)]
    interval=[abs(1/d) if d else math.inf for d in delta]
    for _ in range(64):
        axis=min(range(3),key=lambda i:crossing[i])
        if crossing[axis] >= 1-1e-7:
            return True
        entered=crossing[axis]
        cell[axis]+=step[axis]; crossing[axis]+=interval[axis]
        point=Vec3i(*cell)
        if point!=target and world.block_at(point) not in AIR and point not in world.replaceable:
            # An endpoint infinitesimally inside its clicked support is valid.
            return point==Vec3i(*(math.floor(v) for v in hit)) and entered > 1-1e-3
    return False


@dataclass(frozen=True)
class InteractionCandidate:
    feet: Vec3i
    cost: float


def orientation(properties: dict[str, str]) -> tuple[float | None, float | None]:
    # Horizontal placement normally faces opposite the player's viewing direction.
    yaw = {"north": 0.0, "south": 180.0, "west": -90.0, "east": 90.0}.get(properties.get("facing"))
    pitch = -80.0 if properties.get("half") == "top" else None
    return yaw, pitch


def can_interact(operation: BuildOperation, world: WorldState, feet: Vec3i, reach: float = 3.8) -> bool:
    target = operation.position
    if feet in (target, target.offset(dy=-1)) or (operation.kind == OperationKind.BREAK and feet.offset(dy=-1) == target) or world.block_at(feet) not in AIR or world.block_at(feet.offset(dy=1)) not in AIR:
        return False
    if world.is_hazardous(feet) or world.is_hazardous(feet.offset(dy=-1)):
        return False
    strict = world.observed_bounds is not None
    flight = world.player.creative and world.player.flying
    if strict and flight and (world.block_at(feet.offset(dy=2)) not in AIR or not world.observed_bounds.contains(feet.offset(dy=2))):
        return False
    if strict and (not world.observed_bounds.contains(feet) or (not flight and feet.offset(dy=-1) not in world.solid)):
        return False
    eye = world.player.eye if feet == world.player.position and world.player.eye else (feet.x+.5, feet.y+1.62+(.35 if flight else 0), feet.z+.5)
    if (strict and operation.kind == OperationKind.BREAK and feet.y-1 <= target.y <= feet.y+1
            and target.x < eye[0]+.31 and target.x+1 > eye[0]-.31
            and target.z < eye[2]+.31 and target.z+1 > eye[2]-.31):
        return False  # Same conservative fractional footprint as the guarded adapter.
    if strict and operation.kind == OperationKind.PLACE:
        bottom = eye[1]-1.62
        if (target.x < eye[0]+.3 and target.x+1 > eye[0]-.3
                and target.z < eye[2]+.3 and target.z+1 > eye[2]-.3
                and target.y < bottom+1.8 and target.y+1 > bottom):
            return False  # Integer feet alone misses collisions near a cell edge.
        if (flight and feet.y <= target.y <= feet.y+2
                and target.x < eye[0]+.31 and target.x+1 > eye[0]-.31
                and target.z < eye[2]+.31 and target.z+1 > eye[2]-.31):
            # Preserve the same three-cell clearance required by flight routing
            # AFTER placement. A lowered/crouching eye can otherwise permit a
            # ceiling above the player and invalidate every subsequent route.
            return False
    hits = []
    if operation.kind == OperationKind.BREAK:
        # Breaking a floating owned platform targets the block itself; it does
        # not require the support face needed to place a new block.
        hits.append((target.x+.5, target.y+.5, target.z+.5))
    for dx,dy,dz in ((0,-1,0),(0,1,0),(-1,0,0),(1,0,0),(0,0,-1),(0,0,1)):
        support=target.offset(dx,dy,dz)
        if strict and (support not in world.solid or world.block_at(support) in AIR):
            continue
        hit=(support.x+.5-dx*.4999,support.y+.5-dy*.4999,support.z+.5-dz*.4999)
        if strict and sum((eye[j]-hit[j])*(-d) for j,d in enumerate((dx,dy,dz))) <= 0:
            continue  # Cannot click the back of an occluding support face.
        hits.append(hit)
    if not strict:
        hits.append((target.x+.5,target.y+.5,target.z+.5))
    for hit in hits:
        delta=tuple(hit[j]-eye[j] for j in range(3))
        if sum(v*v for v in delta)>reach*reach:
            continue
        if _clear_ray(world,eye,hit,target):
            return True
    return False


def candidates(operation: BuildOperation, world: WorldState, reach: float = 4.5,
               reserved: set[Vec3i] | None = None) -> list[InteractionCandidate]:
    target = operation.position
    result: list[InteractionCandidate] = []
    strict = world.observed_bounds is not None
    for dy in range(-5, 3):
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                feet = target.offset(dx, dy, dz)
                if abs(dx) + abs(dz) == 0:
                    continue
                if strict and not all(world.observed_bounds.contains(p) for p in (feet, feet.offset(dy=1), feet.offset(dy=-1))):
                    continue
                if world.block_at(feet) not in AIR or world.block_at(feet.offset(dy=1)) not in AIR:
                    continue
                if world.is_hazardous(feet) or world.is_hazardous(feet.offset(dy=-1)):
                    continue
                if strict and not (world.player.creative and world.player.flying) and feet.offset(dy=-1) not in world.solid:
                    continue
                eye = (feet.x + .5, feet.y + 1.62, feet.z + .5)
                delta = (target.x + .5 - eye[0], target.y + .5 - eye[1], target.z + .5 - eye[2])
                distance = math.sqrt(sum(v * v for v in delta))
                if not strict and distance > reach:
                    continue
                blocked = False
                for i in (() if strict else range(1, 20)):
                    point = Vec3i(*(math.floor(eye[j] + delta[j] * i / 20) for j in range(3)))
                    if point != target and world.block_at(point) not in AIR and point not in world.replaceable:
                        blocked = True
                        break
                if blocked:
                    continue
                if strict and not can_interact(operation, world, feet, reach):
                    continue
                # Prefer closer interaction faces and avoid standing in imminent construction cells.
                cost = feet.distance_squared(world.player.position) + distance * 4 + abs(dy) * 2
                # A wall/window ledge is collision-solid but not a useful walking
                # platform. Prefer the current floor over climbing each new block.
                cost += abs(feet.y-world.player.position.y) * (2 if world.player.creative and world.player.flying else 25)
                if reserved and (feet in reserved or feet.offset(dy=1) in reserved):
                    cost += 8
                result.append(InteractionCandidate(feet, cost))
    return sorted(result, key=lambda c: (c.cost, c.feet))

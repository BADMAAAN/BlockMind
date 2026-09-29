from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Bounds, Design, StructureComponent, Vec3i


@dataclass(frozen=True)
class HouseSpecification:
    width: int = 17
    depth: int = 13
    floors: int = 2
    floor_height: int = 4
    wall_material: str = "minecraft:white_concrete"
    accent_material: str = "minecraft:dark_oak_planks"
    window_material: str = "minecraft:glass_pane"
    pool: bool = True


class PromptInterpreter:
    """Deterministic MVP interpreter; replaceable by an LLM-backed implementation."""

    def interpret(self, prompt: str) -> HouseSpecification:
        text = prompt.lower()
        floors = 2 if any(token in text for token in ("two-story", "two storey", "two-story", "2-story")) else 1
        size = re.search(r"(\d+)\s*[x×]\s*(\d+)", text)
        width, depth = (int(size.group(1)), int(size.group(2))) if size else (17, 13)
        width = max(9, min(width, 41))
        depth = max(9, min(depth, 41))
        return HouseSpecification(
            width=width,
            depth=depth,
            floors=floors,
            wall_material="minecraft:white_concrete" if "white concrete" in text else "minecraft:smooth_quartz",
            accent_material="minecraft:dark_oak_planks" if "dark oak" in text else "minecraft:spruce_planks",
            pool="pool" in text,
        )


class ModernHouseArchitect:
    def create_design(self, spec: HouseSpecification, origin: Vec3i) -> Design:
        house_max_y = origin.y + spec.floors * spec.floor_height + 1
        pool_extra = 8 if spec.pool else 0
        bounds = Bounds(origin, origin.offset(spec.width - 1, house_max_y - origin.y, spec.depth + pool_extra - 1))
        components: list[StructureComponent] = []

        def component(cid: str, kind: str, low: Vec3i, high: Vec3i, material: str | None, parent: str | None = None):
            components.append(StructureComponent(cid, kind, Bounds(low, high), material, parent))

        component("foundation", "foundation", origin, origin.offset(spec.width - 1, 0, spec.depth - 1), spec.accent_material)
        for floor in range(spec.floors):
            base_y = origin.y + 1 + floor * spec.floor_height
            parent = f"floor_{floor + 1}"
            component(parent, "floor", Vec3i(origin.x, base_y, origin.z),
                      Vec3i(origin.x + spec.width - 1, base_y + spec.floor_height - 1, origin.z + spec.depth - 1), None)
            component(f"{parent}.slab", "floor_slab", Vec3i(origin.x, base_y, origin.z),
                      Vec3i(origin.x + spec.width - 1, base_y, origin.z + spec.depth - 1), spec.accent_material, parent)
            for side in ("north", "south", "west", "east"):
                component(f"{parent}.wall_{side}", "wall", Vec3i(origin.x, base_y + 1, origin.z),
                          Vec3i(origin.x + spec.width - 1, base_y + spec.floor_height - 1, origin.z + spec.depth - 1),
                          spec.wall_material, parent)
        roof_y = origin.y + spec.floors * spec.floor_height + 1
        component("roof", "flat_roof", Vec3i(origin.x, roof_y, origin.z),
                  Vec3i(origin.x + spec.width - 1, roof_y, origin.z + spec.depth - 1), spec.accent_material)
        component("entrance", "entrance", Vec3i(origin.x + spec.width // 2, origin.y + 2, origin.z),
                  Vec3i(origin.x + spec.width // 2, origin.y + 3, origin.z), "minecraft:dark_oak_door")
        if spec.pool:
            component("pool", "pool", Vec3i(origin.x + 3, origin.y, origin.z + spec.depth + 2),
                      Vec3i(origin.x + spec.width - 4, origin.y + 1, origin.z + spec.depth + 6), "minecraft:water")
        return Design("small_modern_house", origin, bounds, components, spec.__dict__.copy())

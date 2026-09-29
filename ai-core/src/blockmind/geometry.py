from __future__ import annotations

from collections import Counter

from .models import BuildOperation, BuildPlan, Design, OperationKind, Vec3i


class ModernHouseGeometry:
    """Expands semantic house components into deterministic block operations."""

    def generate(self, design: Design) -> BuildPlan:
        p = design.parameters
        origin = design.origin
        width, depth = p["width"], p["depth"]
        floors, floor_height = p["floors"], p["floor_height"]
        wall, accent, glass = p["wall_material"], p["accent_material"], p["window_material"]
        desired: dict[Vec3i, tuple[str, str]] = {}

        def put(position: Vec3i, block: str, component: str) -> None:
            desired[position] = (block, component)

        for x in range(width):
            for z in range(depth):
                put(origin.offset(x, 0, z), accent, "foundation")

        door_x = width // 2
        for floor in range(floors):
            base_y = 1 + floor * floor_height
            slab_component = f"floor_{floor + 1}.slab"
            for x in range(width):
                for z in range(depth):
                    put(origin.offset(x, base_y, z), accent, slab_component)
            for y in range(base_y + 1, base_y + floor_height):
                for x in range(width):
                    for z, side in ((0, "north"), (depth - 1, "south")):
                        is_door = floor == 0 and side == "north" and x == door_x and y <= base_y + 2
                        window = 2 <= x <= width - 3 and x % 3 != 0 and y in (base_y + 1, base_y + 2)
                        if not is_door:
                            put(origin.offset(x, y, z), glass if window else wall, f"floor_{floor + 1}.wall_{side}")
                for z in range(1, depth - 1):
                    for x, side in ((0, "west"), (width - 1, "east")):
                        window = 2 <= z <= depth - 3 and z % 3 != 0 and y in (base_y + 1, base_y + 2)
                        put(origin.offset(x, y, z), glass if window else wall, f"floor_{floor + 1}.wall_{side}")

        roof_y = floors * floor_height + 1
        for x in range(width):
            for z in range(depth):
                put(origin.offset(x, roof_y, z), accent, "roof")

        # Door is represented as lower/upper states by the adapter when available; MVP places lower item once.
        put(origin.offset(door_x, 2, 0), "minecraft:dark_oak_door", "entrance")

        if p["pool"]:
            x0, x1 = 3, width - 4
            z0, z1 = depth + 2, depth + 6
            for x in range(x0 - 1, x1 + 2):
                for z in range(z0 - 1, z1 + 2):
                    border = x in (x0 - 1, x1 + 1) or z in (z0 - 1, z1 + 1)
                    put(origin.offset(x, 0, z), "minecraft:smooth_quartz" if border else "minecraft:water", "pool")

        operations = [BuildOperation(OperationKind.PLACE, pos, block, component)
                      for pos, (block, component) in sorted(desired.items(), key=lambda item: (item[0].y, item[0].z, item[0].x))]
        materials = dict(Counter(op.block for op in operations if op.block and op.block != "minecraft:air"))
        return BuildPlan(design, operations, materials, design.bounds.expanded(2))

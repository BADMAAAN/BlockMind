"""Reproducible route-only comparison. No claim about actual player movement."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai-core/src"))
from blockmind.execution import LegacyBuildPlanOptimizer
from blockmind.models import BuildOperation, OperationKind, Vec3i
from blockmind.navigation import SafeSimulatedNavigationProvider
from blockmind.runtime import BlockMindAgent
from blockmind.scheduler import ConstructionScheduler, route_quality
from blockmind.simulation import SimulatedMinecraftPort


def legacy_order(plan):
    """Frozen 19db2c8 route algorithm, used only as the measured baseline."""
    return LegacyBuildPlanOptimizer().optimize(plan)


def main():
    prompt = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."
    project = BlockMindAgent(SimulatedMinecraftPort(), SafeSimulatedNavigationProvider()).plan(prompt, Vec3i(0,64,0))
    house = list(project.plan.operations)
    fixtures = {"foundation_64": [op for op in house if op.component_id == "foundation"][:64],
                "vertical_28": [op for op in house if 0<=op.position.x<3 and 0<=op.position.z<3 and 64<=op.position.y<=67],
                "full_house": house}
    fixtures["four_glass_sides"] = [BuildOperation(OperationKind.PLACE, position, "minecraft:glass_pane", "floor_1.wall_"+side)
        for i in range(4) for side,position in (("north",Vec3i(2+i,66,0)), ("south",Vec3i(2+i,66,12)),
                                               ("east",Vec3i(16,66,2+i)), ("west",Vec3i(0,66,2+i)))]
    results = {"mode":"ROUTE_ONLY_NOT_LIVE", "baseline_commit":"19db2c8", "fixtures":{}}
    for name, operations in fixtures.items():
        project.plan.operations = operations
        before, after = legacy_order(project.plan), ConstructionScheduler().optimize(project.plan)
        results["fixtures"][name] = {"operations":len(operations), "before":route_quality(before), "after":route_quality(after),
            "identical_geometry": {op.id for op in before} == {op.id for op in after}}
    print(json.dumps(results, indent=2))


if __name__ == "__main__": main()

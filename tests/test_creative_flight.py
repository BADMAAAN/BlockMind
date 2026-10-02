import unittest

from blockmind.execution import ExecutionConfig
from blockmind.interaction import can_interact, candidates
from blockmind.models import Bounds, BuildOperation, OperationKind, PlayerState, Vec3i, WorldState


class CreativeFlightTests(unittest.TestCase):
    def test_placement_preserves_navigation_clearance_above_lowered_flight_eye(self):
        feet=Vec3i(0,70,0)
        world=WorldState(PlayerState(feet,flying=True,eye=(.5,71.27,.5)),
                         observed_bounds=Bounds(Vec3i(-5,64,-5),Vec3i(5,75,5)))
        target=feet.offset(dy=2)
        support=target.offset(dx=1)
        world.blocks[support]='minecraft:stone'; world.solid.add(support)
        operation=BuildOperation(OperationKind.PLACE,target,'minecraft:stone','cap')
        self.assertFalse(can_interact(operation,world,feet,4.5))
        # A neighbouring, clear position can still place the identical cell.
        self.assertTrue(can_interact(operation,world,feet.offset(dz=1),4.5))

    def test_voxel_ray_detects_thin_diagonal_occluding_edge(self):
        from blockmind.interaction import _clear_ray
        world=WorldState(PlayerState(Vec3i(0,70,0)))
        edge=Vec3i(0,70,1); world.blocks[edge]='minecraft:stone'
        eye=(.1,70.5,.1); hit=(2.9,70.5,2.901); target=Vec3i(2,70,2)
        self.assertFalse(_clear_ray(world,eye,hit,target))
        world.blocks.clear()
        self.assertTrue(_clear_ray(world,eye,hit,target))
        world.blocks[Vec3i(2,70,2)]='minecraft:stone'
        self.assertTrue(_clear_ray(world,(4.5,70.5,2.5),(2.9999,70.5,2.5),Vec3i(3,70,2)))

    def test_support_top_face_cannot_be_clicked_from_below(self):
        feet=Vec3i(-1,67,0)
        world=WorldState(PlayerState(feet,flying=True),observed_bounds=Bounds(Vec3i(-5,60,-5),Vec3i(5,75,5)))
        target=Vec3i(1,70,0); support=target.offset(dy=-1)
        world.blocks[support]='minecraft:stone'; world.solid.add(support)
        op=BuildOperation(OperationKind.PLACE,target,'minecraft:stone','leg')
        self.assertFalse(can_interact(op,world,feet,4.5))

    def test_flight_is_opt_in_and_boolean(self):
        self.assertFalse(ExecutionConfig().creative_flight)
        self.assertTrue(ExecutionConfig(creative_flight=True).to_dict()["creative_flight"])
        with self.assertRaises(ValueError):
            ExecutionConfig(creative_flight="true")

    def test_only_observed_creative_flight_allows_airborne_interaction(self):
        feet = Vec3i(-1, 70, 0)
        target = Vec3i(1, 70, 0)
        world = WorldState(PlayerState(feet), observed_bounds=Bounds(Vec3i(-5, 64, -5), Vec3i(5, 75, 5)))
        support = target.offset(dy=-1)
        world.blocks[support] = "minecraft:stone"
        world.solid.add(support)
        op = BuildOperation(OperationKind.PLACE,target,"minecraft:stone","leg")
        self.assertFalse(can_interact(op,world,feet))
        world.player.flying = True
        self.assertTrue(can_interact(op,world,feet))
        self.assertIn(feet,[c.feet for c in candidates(op,world)])
        world.player.creative = False
        self.assertFalse(can_interact(op,world,feet))

    def test_flight_still_requires_support_loaded_cells_and_clear_body(self):
        feet = Vec3i(-1,70,0)
        target = Vec3i(1,70,0)
        world = WorldState(PlayerState(feet,flying=True),observed_bounds=Bounds(Vec3i(-5,64,-5),Vec3i(5,75,5)))
        op = BuildOperation(OperationKind.PLACE,target,"minecraft:stone","leg")
        self.assertFalse(can_interact(op,world,feet))
        support = target.offset(dy=-1)
        world.blocks[support] = "minecraft:stone"; world.solid.add(support)
        self.assertTrue(can_interact(op,world,feet))
        world.blocks[feet.offset(dy=2)] = "minecraft:stone"
        self.assertFalse(can_interact(op,world,feet))
        world.blocks.clear()
        world.observed_bounds = Bounds(Vec3i(0,64,-5),Vec3i(5,75,5))
        self.assertFalse(can_interact(op,world,feet))

    def test_precise_body_prevents_placement_through_neighbour_cell_edge(self):
        feet = Vec3i(0,70,0)
        world = WorldState(PlayerState(feet,flying=True,eye=(.92,71.97,.5)),
                           observed_bounds=Bounds(Vec3i(-5,64,-5),Vec3i(5,75,5)))
        target = Vec3i(1,70,0); support = target.offset(dy=-1)
        world.blocks[support] = "minecraft:stone"; world.solid.add(support)
        op = BuildOperation(OperationKind.PLACE,target,"minecraft:stone","leg")
        self.assertFalse(can_interact(op,world,feet))
        world.player.eye = (.5,71.97,.5)
        self.assertTrue(can_interact(op,world,feet))

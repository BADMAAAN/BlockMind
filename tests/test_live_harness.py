import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from blockmind.models import Vec3i
from blockmind.reference_builds import enderman_project
from blockmind.runtime import ProjectStore, ValidationReport
from scripts.live_acceptance import revalidate_owned_world


class ReadOnlyInspectionTests(unittest.IsolatedAsyncioTestCase):
    async def check_inspection(self, before, after, dimension='minecraft:overworld'):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            project=enderman_project(Vec3i(0,64,0)); project.dimension='minecraft:overworld'
            source=ProjectStore(root/'source').save(project)
            server=SimpleNamespace(start=AsyncMock(),wait_connected=AsyncMock(),close=AsyncMock(),
                request=AsyncMock(side_effect=[before,after]),metrics=SimpleNamespace(snapshot=lambda:{}))
            port=SimpleNamespace(world_state=AsyncMock(return_value=SimpleNamespace(player=SimpleNamespace(dimension=dimension))))
            validate=AsyncMock(return_value=ValidationReport(1243,1243,0,0))
            with patch('blockmind.network.FabricSessionServer',return_value=server), patch('blockmind.network.FabricMinecraftPort',return_value=port), patch('blockmind.runtime.Validator.validate',validate):
                if dimension != project.dimension or before.get('issuedPlacements') is None or after.get('issuedPlacements') != before.get('issuedPlacements'):
                    with self.assertRaises(RuntimeError): await revalidate_owned_world(source,root/'inspection')
                    self.assertFalse((root/'inspection/projects').exists())
                else:
                    self.assertEqual(await revalidate_owned_world(source,root/'inspection'),0)
                    saved=ProjectStore(root/'inspection/projects').load(root/'inspection/projects'/source.name)
                    self.assertEqual(saved.performance['mutation_attempts'],0)
                    self.assertEqual(saved.performance['mode'],'READ_ONLY_REVALIDATION_NOT_BUILD_TIMING')
            server.close.assert_awaited_once()
            if dimension != project.dimension:
                validate.assert_not_awaited(); server.request.assert_not_awaited()
            else:
                validate.assert_awaited_once()
                self.assertEqual([call.args[0] for call in server.request.await_args_list],['performance','performance'])

    async def test_read_only_full_scan_records_zero_mutations(self):
        await self.check_inspection({'issuedPlacements':0},{'issuedPlacements':0})

    async def test_changed_placement_counter_is_rejected(self):
        await self.check_inspection({'issuedPlacements':0},{'issuedPlacements':1})

    async def test_missing_counters_are_not_fabricated_zero_mutations(self):
        await self.check_inspection({},{})

    async def test_wrong_dimension_stops_before_scan_or_mutation(self):
        await self.check_inspection({'issuedPlacements':0},{'issuedPlacements':0},'minecraft:the_nether')

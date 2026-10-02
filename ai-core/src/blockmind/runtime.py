from __future__ import annotations

import asyncio
import json
import logging
import os
from time import perf_counter, sleep
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .design import IntentProvider, ModernHouseArchitect, PromptInterpreter
from .geometry import ModernHouseGeometry
from .interaction import AIR, candidates, can_interact
from .models import (Bounds, BuildOperation, OperationKind, OperationStatus, ProjectState,
                     ProjectStatus, Vec3i, WorldState)
from .navigation import NavigationGoal, NavigationGoalKind, NavigationProvider
from .execution import ExecutionConfig, OperationClass, classify
from .performance import PerformanceMetrics, counter_delta
from .scheduler import ConstructionScheduler, zone_id, route_quality
from .bursts import AdaptiveBurstController, BuildBurst

LOG = logging.getLogger("blockmind")


class ExecutionStopped(RuntimeError):
    """Acknowledged local STOP interrupted a read; never a mutation replay cue."""


class MinecraftPort(ABC):
    @abstractmethod
    async def world_state(self) -> WorldState: ...

    @abstractmethod
    async def place_block(self, operation: BuildOperation) -> bool: ...

    @abstractmethod
    async def break_block(self, operation: BuildOperation) -> bool: ...

    @abstractmethod
    async def block_at(self, position: Vec3i) -> str: ...

    async def close(self) -> None:
        return None

    async def inspect_block(self, position: Vec3i) -> tuple[str, dict[str, str]]:
        return await self.block_at(position), {}

    async def scan_region(self, bounds: Bounds):
        return None

    async def approve(self, project: ProjectState) -> None:
        return None

    async def control(self, kind: str) -> None:
        return None

    async def interaction_world(self, target: Vec3i) -> WorldState:
        return await self.world_state()

    supports_fast = False

    async def configure_execution(self, config):
        return None

    async def finish_execution(self):
        return None

    async def place_batch(self, operations):
        return [{"id": op.id, "issued": await self.place_block(op)} for op in operations]

    async def validate_operations(self, operations):
        mismatches = set()
        for op in operations:
            block, props = await self.inspect_block(op.position)
            if block != op.block or any(props.get(k) != v for k, v in op.properties.items()):
                mismatches.add(op.id)
        return mismatches


class ControlState:
    def __init__(self) -> None:
        self._gate = asyncio.Event()
        self._gate.set()
        self.stopped = False

    def pause(self) -> None:
        self._gate.clear()

    def resume(self) -> None:
        if not self.stopped:
            self._gate.set()

    def stop(self) -> None:
        self.stopped = True
        self._gate.set()

    async def wait(self) -> None:
        await self._gate.wait()


@dataclass(frozen=True)
class ValidationReport:
    expected: int
    correct: int
    missing: int
    incorrect: int
    extra_permanent: int = 0
    temporary_remaining: int = 0

    @property
    def verified(self) -> bool:
        return (self.expected == self.correct and self.missing == 0 and self.incorrect == 0
                and self.extra_permanent == 0 and self.temporary_remaining == 0)


class Builder:
    def __init__(self, port: MinecraftPort, navigation: NavigationProvider,
                 control: ControlState | None = None, max_attempts: int = 3, config: ExecutionConfig | None = None) -> None:
        self.port = port
        self.navigation = navigation
        self.control = control or ControlState()
        self.max_attempts = max_attempts
        self.checkpoint: Callable[[ProjectState], object] | None = None
        self.config = config or ExecutionConfig(speed_profile="safe")
        self.metrics = PerformanceMetrics()
        self._placed_ids: set[str] = set()
        self._ordered = None
        self._access_levels = set()
        self._placed_at = {}

    def _schedule(self, project, world):
        scheduler = ConstructionScheduler()
        ordered = scheduler.optimize(project.plan, start=world.player.position,
            completed=project.completed_operation_ids, active_zone=project.scheduler.get("active_zone"), direction=project.scheduler.get("direction"))
        if getattr(self, "legacy_scheduler", False):
            from .execution import LegacyBuildPlanOptimizer
            ordered = LegacyBuildPlanOptimizer().optimize(project.plan)
            scheduler.direction = None
            scheduler.decisions = [{"zone": zone_id(op), "strategy": "legacy_barriers", "reason": "A/B_baseline"}
                for i,op in enumerate(ordered) if i==0 or zone_id(op)!=zone_id(ordered[i-1])]
        project.scheduler.update({"version": 1, "algorithm": "legacy_19db2c8" if getattr(self,"legacy_scheduler",False) else "global",
            "direction": scheduler.direction, "decisions": scheduler.decisions,
            "planned_route": route_quality(ordered), "raw_route": route_quality(project.plan.operations)})
        for decision in scheduler.decisions:
            LOG.info("SCHEDULER zone=%s strategy=%s reason=%s", decision["zone"], decision["strategy"], decision["reason"])
        self._ordered = ordered
        return ordered

    def _record_operation(self, project, operation):
        name = zone_id(operation)
        previous = project.scheduler.get("active_zone")
        history = project.scheduler.setdefault("recent_zones", [])
        if previous != name:
            self.metrics.counts["region_switches"] += bool(previous)
            self.metrics.counts["component_switches"] += bool(previous)
            self.metrics.counts["backtracks"] += name in history[-4:]
            history.append(name)
            project.scheduler["recent_zones"] = history[-16:]
            project.scheduler["active_zone"] = name
            LOG.info("WORK_ZONE enter=%s", name)
        project.scheduler["current_operation"] = operation.id
        recent = project.scheduler.setdefault("recent_operations", [])
        recent.append({"id": operation.id, "position": operation.position.to_dict(), "block": operation.block})
        project.scheduler["recent_operations"] = recent[-16:]

    async def _navigate(self, goal, world, project):
        self.metrics.counts["navigation_requests"] += 1
        project.scheduler["navigation_goal"] = goal.target.to_dict()
        with self.metrics.measure("navigation"):
            result = await self.navigation.navigate(goal, world)
        project.scheduler["navigation_goal"] = None
        if not result.success:
            from .navigation import failure_kind
            kind = failure_kind(result.reason)
            self.metrics.counts["navigation_failure_"+kind] += 1
            project.scheduler.setdefault("navigation_failures", []).append({"kind": kind,
                "target": goal.target.to_dict(), "reason": result.reason})
            project.scheduler["navigation_failures"] = project.scheduler["navigation_failures"][-32:]
        return result

    @staticmethod
    def _complete(project: ProjectState, operation: BuildOperation) -> None:
        operation.status = OperationStatus.COMPLETE
        operation.error = None
        project.last_observations.append({"position": operation.position.to_dict(), "block": "minecraft:air" if operation.kind == OperationKind.BREAK else operation.block,
            "properties": operation.properties.copy(), "operation": operation.id})
        project.last_observations[:] = project.last_observations[-256:]
        project.failures[:] = [entry for entry in project.failures if entry.get("operation") != operation.id]
        if operation.id not in project.completed_operation_ids:
            project.completed_operation_ids.append(operation.id)
        if operation.kind == OperationKind.PLACE and not operation.temporary:
            project.temporary_blocks[:] = [entry for entry in project.temporary_blocks
                if Vec3i(**entry["position"]) != operation.position]

    async def _gate(self, project: ProjectState) -> bool:
        with self.metrics.measure("control_wait"):
            await self.control.wait()
        if self.control.stopped:
            project.status = ProjectStatus.STOPPED
            return False
        with self.metrics.measure("observation"):
            world = await self.port.world_state()
        if project.dimension is not None and project.dimension != world.player.dimension:
            raise RuntimeError("dimension changed; stop and reconcile in the original dimension")
        return True

    async def reconcile(self, project: ProjectState) -> None:
        project.completed_operation_ids.clear()
        project.failures.clear()
        scanned = await self.port.scan_region(project.plan.temporary_area or project.plan.approved_area)
        summary = Counter()
        for operation in project.plan.operations:
            operation.status = OperationStatus.PENDING
            operation.error = None
            if scanned is None:
                satisfied = await self._already_satisfied(operation)
            else:
                block, props = scanned.get(operation.position, ("minecraft:air", {}))
                satisfied = block == ("minecraft:air" if operation.kind == OperationKind.BREAK else operation.block) and all(props.get(k)==v for k,v in operation.properties.items())
                summary["correct" if satisfied else "missing" if block in AIR else "incorrect"] += 1
            if satisfied:
                self._complete(project, operation)
        if scanned is not None:
            for entry in list(project.temporary_blocks):
                actual = scanned.get(Vec3i(**entry["position"]), ("minecraft:air", {}))[0]
                if actual in AIR: project.temporary_blocks.remove(entry)
                else: summary["owned_temporary" if actual == entry["block"] else "temporary_conflict"] += 1
        project.scheduler["reconciliation"] = dict(summary)
        project.scheduler["active_batch"] = []
        project.scheduler["navigation_goal"] = None

    async def execute(self, project: ProjectState,
                      on_progress: Callable[[ProjectState, BuildOperation], None] | None = None) -> ProjectState:
        world = await self.port.world_state()
        self._schedule(project, world)
        if self.config.speed_profile != "safe" and self.config.adaptive_verification and self.config.component_validation and world.player.creative and self.port.supports_fast:
            await self._execute_fast(project, on_progress)
        else:
            await self._execute_strict(project, on_progress, cleanup=False)
        # A failed approach does not prevent reachable independent work. Return
        # once after progress elsewhere, never endlessly repeat a failed zone.
        deferred = [op for op in self._ordered if op.status == OperationStatus.FAILED and
            (op.error or "").startswith(("navigation:", "no safe interaction", "dependency temporarily"))]
        if 0 < len(deferred) < 10 and project.completed_operation_ids and not self.control.stopped:
            project.scheduler["postponed_operations"] = [op.id for op in deferred]
            self.metrics.counts["postponed_operations"] += len(deferred)
            await self._execute_strict(project, on_progress, deferred, cleanup=False)
        if not self.control.stopped:
            await self._safe_cleanup(project)
        project.status = ProjectStatus.STOPPED if self.control.stopped else ProjectStatus.FAILED if project.failures else ProjectStatus.COMPLETE
        return project

    async def _execute_strict(self, project, on_progress=None, operations=None, cleanup=True):
        project.status = ProjectStatus.BUILDING
        consecutive_failures = 0
        ordered = operations if operations is not None else self._ordered or self._schedule(project, await self.port.world_state())
        for index, operation in enumerate(ordered):
            self._record_operation(project, operation)
            if operations is None: await self._prepare_zone_access(operation, project)
            if any(dep not in project.completed_operation_ids for dep in operation.depends_on):
                self._fail(project, operation, "dependency temporarily blocked")
                continue
            if self.control.stopped or not await self._gate(project):
                project.status = ProjectStatus.STOPPED
                return project
            if operation.destructive and not project.plan.approved_area.contains(operation.position):
                operation.status = OperationStatus.FAILED
                operation.error = "destructive operation outside approved area"
                project.failures.append({"operation": operation.id, "reason": operation.error})
                project.status = ProjectStatus.FAILED
                return project
            if await self._already_satisfied(operation):
                self._complete(project, operation)
                if on_progress:
                    on_progress(project, operation)
                continue
            if operation.verify_only:
                self._fail(project, operation, "companion block state not observed")
                continue
            operation.status = OperationStatus.RUNNING
            temporary_scaffold: list[Vec3i] = []
            failed_candidates = set()
            for attempt in range(self.max_attempts):
                if not await self._gate(project):
                    return project
                operation.attempts += 1
                if self.checkpoint:
                    with self.metrics.measure("checkpoint_io"): self.checkpoint(project)
                with self.metrics.measure("observation"):
                    world = await self.port.interaction_world(operation.position)
                reserved = {op.position for op in ordered[index + 1:index + 9]}
                with self.metrics.measure("interaction_planning"):
                    options = candidates(operation, world, reach=self.config.placement_radius, reserved=reserved)
                    options = [candidate for candidate in options if candidate.feet not in failed_candidates
                               and (world.observed_bounds is None or self._construction_feet_allowed(operation,candidate.feet,project))]
                if not options:
                    temporary_scaffold = await self._install_scaffold(operation, project)
                    await self._install_access(operation, project)
                    options = candidates(operation, await self.port.interaction_world(operation.position), reach=3.8, reserved=reserved)
                    if world.observed_bounds is not None:
                        options = [candidate for candidate in options if self._construction_feet_allowed(operation,candidate.feet,project)]
                if not options:
                    self._fail(project, operation, "no safe interaction position")
                    break
                current = self.config.reuse_interaction_positions and world.observed_bounds is not None and self._construction_feet_allowed(operation,world.player.position,project) and can_interact(operation, world, world.player.position, self.config.placement_radius)
                if current:
                    from .navigation import NavigationResult
                    nav = NavigationResult(True, world.player.position, "reuse interaction position")
                    self.metrics.counts["interaction_reuses"] += 1
                else:
                    nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION,
                        options[min(attempt, len(options) - 1)].feet, tolerance=.75), world, project)
                # Controls may arrive while navigation awaits a response.
                if not await self._gate(project):
                    return project
                if not nav.success:
                    failed_candidates.add(options[min(attempt, len(options) - 1)].feet)
                    operation.error = f"navigation: {nav.reason}"
                    LOG.warning("navigation failed", extra={"reason": operation.error, "operation_id": operation.id,
                        "target": options[min(attempt, len(options) - 1)].feet.to_dict()})
                    if attempt + 1 < self.max_attempts:
                        await self._install_access(operation, project)
                    continue
                if world.observed_bounds is not None:
                    # Arrival/ability/pose may differ from the virtual candidate.
                    # Recheck the ACTUAL feet and terrain before a strict mutation.
                    world = await self.port.interaction_world(operation.position)
                    if (not self._construction_feet_allowed(operation,world.player.position,project)
                            or not can_interact(operation,world,world.player.position,self.config.placement_radius)):
                        failed_candidates.add(options[min(attempt,len(options)-1)].feet)
                        failed_candidates.add(world.player.position)
                        operation.error = 'actual arrival pose is not a safe interaction position'
                        continue
                actual = await self.port.block_at(operation.position)
                if operation.kind == OperationKind.PLACE and actual not in AIR and not await self._already_satisfied(operation):
                    original = next((e["block"] for e in project.baseline if Vec3i(**e["position"]) == operation.position), "minecraft:air")
                    if not project.baseline_captured or original not in AIR or not project.plan.approved_area.contains(operation.position):
                        self._fail(project, operation, "existing block conflict; explicit clearing required")
                        break
                    clear = BuildOperation(OperationKind.BREAK, operation.position, None, operation.component_id, destructive=True)
                    if not await self.port.break_block(clear) or await self.port.block_at(operation.position) not in AIR:
                        operation.error = "local clearing failed"
                        continue
                with self.metrics.measure("placement"):
                    self.metrics.counts["operation_attempts"] += 1
                    acted = await (self.port.place_block(operation) if operation.kind == OperationKind.PLACE
                                   else self.port.break_block(operation))
                if acted and await self._already_satisfied(operation):
                    self._complete(project, operation)
                    if operation.kind == OperationKind.PLACE:
                        self._placed_ids.add(operation.id)
                        self._placed_at[operation.id] = (await self.port.world_state()).player.position
                        self.metrics.counts["blocks_placed"] = len(self._placed_ids)
                    break
                operation.error = getattr(self.port, "last_action_reason", "") or "observed state did not match"
                if operation.kind == OperationKind.PLACE and not temporary_scaffold:
                    temporary_scaffold = await self._install_scaffold(operation, project)
                LOG.warning("action verification failed", extra={"operation_id": operation.id, "reason": operation.error, "attempt": operation.attempts})
            else:
                self._fail(project, operation, operation.error or "verification failed after retries")
            if temporary_scaffold:
                await self._remove_scaffold(temporary_scaffold, project)
            if on_progress:
                on_progress(project, operation)
            if self.checkpoint:
                with self.metrics.measure("checkpoint_io"): self.checkpoint(project)

            consecutive_failures = consecutive_failures + 1 if operation.status == OperationStatus.FAILED else 0
            if consecutive_failures >= 10:
                LOG.error("build halted after repeated local failures; reconcile after fixing the cause")
                break

        if cleanup and not self.control.stopped:
            await self._safe_cleanup(project)
        if operations is None:
            project.status = ProjectStatus.COMPLETE if not project.failures else ProjectStatus.FAILED
        # A strict local fallback/repair is not completion of the enclosing plan.
        return project

    async def _execute_fast(self, project, on_progress=None):
        from itertools import groupby
        adaptive = AdaptiveBurstController(self.config.batch_size)
        with self.metrics.measure("planning"):
            ordered = self._ordered or self._schedule(project, await self.port.world_state())
        required_support_ids = {dep for operation in ordered for dep in operation.depends_on}
        project.status = ProjectStatus.BUILDING
        for _, group in groupby(ordered, key=zone_id):
            group = list(group)
            await self._prepare_zone_access(group[0], project)
            cursor = 0
            processed = set()
            while cursor < len(group):
                if len({failure["operation"] for failure in project.failures}) >= 10:
                    LOG.error("build halted after bounded local failures inside work zone")
                    project.status = ProjectStatus.FAILED
                    return project
                while cursor < len(group) and group[cursor].id in processed:
                    cursor += 1
                if cursor == len(group): break
                await self.control.wait()
                if self.control.stopped:
                    project.status = ProjectStatus.STOPPED; return project
                op = group[cursor]
                self._record_operation(project, op)
                if any(dep not in project.completed_operation_ids for dep in op.depends_on):
                    required = [item for item in group if item.id in op.depends_on and item.id in processed]
                    mismatches = await self.port.validate_operations(required)
                    for item in required:
                        if item.id not in mismatches: self._complete(project,item)
                    if any(dep not in project.completed_operation_ids for dep in op.depends_on):
                        self._fail(project,op,"dependency temporarily blocked"); cursor += 1; continue
                if op.id in project.completed_operation_ids:
                    cursor += 1; continue
                if self.config.speed_profile == "safe" or classify(op) != OperationClass.SIMPLE:
                    await self._execute_strict(project, on_progress, [op], cleanup=False)
                    cursor += 1; continue
                with self.metrics.measure("observation"):
                    world = await self.port.interaction_world(op.position)
                if project.dimension and world.player.dimension != project.dimension:
                    raise RuntimeError("dimension changed")
                # Drain compatible pending work from the CURRENT feet before
                # navigating merely because the route's first target is occluded.
                upcoming = []
                for item in group[cursor:cursor+64]:
                    if item.id in processed or item.id in project.completed_operation_ids: continue
                    if classify(item) != OperationClass.SIMPLE or any(dep not in project.completed_operation_ids for dep in item.depends_on) or item.block != op.block: break
                    upcoming.append(item)
                reachable_here = [item for item in upcoming if
                    (world.observed_bounds is None or self._construction_feet_allowed(item,world.player.position,project))
                    and can_interact(item,world,world.player.position,self.config.placement_radius)]
                with self.metrics.measure("interaction_planning"):
                    options = candidates(op, world, reach=self.config.placement_radius)
                    if world.observed_bounds is not None:
                        options = [candidate for candidate in options if self._construction_feet_allowed(op,candidate.feet,project)]
                current = self.config.reuse_interaction_positions and bool(reachable_here)
                if current is None:
                    current = False
                if not current:
                    if not options:
                        await self._execute_strict(project, on_progress, [op], cleanup=False); cursor += 1; continue
                    with self.metrics.measure("interaction_planning"):
                        construction_cells = {item.position for item in group}
                        safe_options = [candidate for candidate in options if candidate.feet not in construction_cells] or options
                        spot = max(safe_options[:32], key=lambda candidate: (sum(can_interact(item,world,candidate.feet,self.config.placement_radius) for item in upcoming), -candidate.cost))
                    nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION, spot.feet, .75), world, project)
                    if not nav.success:
                        await self._execute_strict(project, on_progress, [op], cleanup=False); cursor += 1; continue
                    with self.metrics.measure("observation"):
                        world = await self.port.interaction_world(op.position)
                await self.control.wait()
                if self.control.stopped:
                    project.status = ProjectStatus.STOPPED; return project
                batch = []
                with self.metrics.measure("interaction_planning"):
                    for candidate in group[cursor:cursor + 64]:
                        if candidate.id in processed: continue
                        if classify(candidate) != OperationClass.SIMPLE or any(dep not in project.completed_operation_ids for dep in candidate.depends_on) or candidate.block != op.block:
                            break
                        if world.observed_bounds is not None and not self._construction_feet_allowed(candidate,world.player.position,project):
                            continue
                        if not can_interact(candidate, world, world.player.position, self.config.placement_radius):
                            continue
                        batch.append(candidate)
                        if len(batch) >= adaptive.size: break
                if not batch:
                    await self._execute_strict(project, on_progress, [op], cleanup=False); cursor += 1; continue
                # Independent supported cubes: far-to-near avoids closing the ray to later cells.
                if world.observed_bounds is not None and all(item.position.offset(dy=-1) in world.solid for item in batch):
                    eye = world.player.eye or (world.player.position.x+.5, world.player.position.y+1.62, world.player.position.z+.5)
                    batch.sort(key=lambda item: -sum((value-eye[axis])**2 for axis,value in enumerate(
                        (item.position.x+.5,item.position.y+.5,item.position.z+.5))))
                burst = BuildBurst(tuple(batch), world.player.position, zone_id(op), project.plan.approved_area,
                                   frozenset(project.completed_operation_ids))
                for item in burst.operations:
                    item.status = OperationStatus.RUNNING; item.attempts += 1
                project.scheduler["active_batch"] = [item.id for item in batch]
                if self.checkpoint:
                    with self.metrics.measure("checkpoint_io"): self.checkpoint(project)
                with self.metrics.measure("placement"):
                    self.metrics.counts["operation_attempts"] += len(batch)
                    outcomes = await self.port.place_batch(batch)
                for item in batch:
                    self._placed_at[item.id] = world.player.position
                project.scheduler["active_batch"] = []
                self.metrics.counts["batches"] += 1
                indexed_outcomes = {value["id"]: value for value in outcomes}
                rejected = [value.get("reason", "unknown") for value in outcomes if not value.get("issued")]
                if rejected:
                    self.metrics.counts["batch_rejections"] += len(rejected)
                    LOG.warning("batch requires local repair", extra={"reason": dict(Counter(rejected))})
                for item in batch:
                    outcome = indexed_outcomes.get(item.id, {})
                    item.error = None if outcome.get("issued") else outcome.get("reason", "batch placement rejected")
                processed.update(item.id for item in batch)
                await self.control.wait()
                if self.control.stopped:
                    project.status = ProjectStatus.STOPPED; return project
                with self.metrics.measure("burst_verification"):
                    burst_mismatches = await self.port.validate_operations(batch)
                adaptive.feedback(attempted=len(batch),
                    issued=sum(bool(indexed_outcomes.get(item.id,{}).get("issued")) for item in batch),
                    verified=sum(item.id not in burst_mismatches for item in batch))
                project.scheduler["burst_feedback"] = adaptive.snapshot()
                self.metrics.counts["burst_verified"] += len(batch)-len(burst_mismatches)
                self.metrics.counts["burst_mismatches"] += len(burst_mismatches)
                for item in batch:
                    if item.id not in burst_mismatches:
                        self._complete(project,item)
                        self._placed_ids.add(item.id)
                self.metrics.counts['blocks_placed'] = len(self._placed_ids)
                # A rejected support cannot wait until the component boundary:
                # its descendants would otherwise accumulate dependency failures.
                support_repairs = [item for item in batch if item.id in burst_mismatches
                                   and item.id in required_support_ids]
                if support_repairs:
                    self.metrics.counts["repair_operations"] += len(support_repairs)
                    await self._execute_strict(project,on_progress,support_repairs,cleanup=False)
                    adaptive.repairs += len(support_repairs)
                    project.scheduler["burst_feedback"] = adaptive.snapshot()
                # Component and final scans remain authoritative; mismatches are
                # repaired locally at the component boundary, never hidden.
            if self.control.stopped:
                project.status = ProjectStatus.STOPPED; return project
            with self.metrics.measure("component_verification"):
                mismatches = await self.port.validate_operations(group)
            repairs = [op for op in group if op.id in mismatches]
            if repairs:
                self.metrics.counts["repair_operations"] += len(repairs)
                await self._execute_strict(project, on_progress, repairs, cleanup=False)
                adaptive.repairs += len(repairs)
                project.scheduler["burst_feedback"] = adaptive.snapshot()
                with self.metrics.measure("component_verification"):
                    mismatches = await self.port.validate_operations(group)
            for item in group:
                if item.id not in mismatches:
                    self._complete(project, item)
                elif item.status != OperationStatus.FAILED:
                    self._fail(project, item, "component checkpoint mismatch after repair")
            self._placed_ids.update(op.id for op in group if op.kind == OperationKind.PLACE and op.id in self._placed_at and op.id not in mismatches)
            self.metrics.counts["blocks_placed"] = len(self._placed_ids)
            project.performance = self.metrics.snapshot()
            if self.checkpoint:
                with self.metrics.measure("checkpoint_io"): self.checkpoint(project)
            LOG.info("PERF component checkpoint", extra={"category": "PERF", "blocks": project.performance})
            if on_progress: on_progress(project, group[-1])
            if len(project.failures) >= 10:
                break
        project.status = ProjectStatus.STOPPED if self.control.stopped else ProjectStatus.FAILED if project.failures else ProjectStatus.COMPLETE
        return project

    async def _already_satisfied(self, operation: BuildOperation) -> bool:
        with self.metrics.measure("verification"):
            actual, props = await self.port.inspect_block(operation.position)
        if operation.kind == OperationKind.BREAK:
            return actual == "minecraft:air"
        return actual == operation.block and all(props.get(k) == v for k, v in operation.properties.items())

    @staticmethod
    def _approach_position(target: Vec3i, world: WorldState) -> Vec3i:
        options = candidates(BuildOperation(OperationKind.PLACE, target, None, "interaction"), world)
        if not options:
            raise ValueError("no safe interaction position")
        return options[0].feet

    @staticmethod
    def _fail(project: ProjectState, operation: BuildOperation, reason: str) -> None:
        operation.status = OperationStatus.FAILED
        operation.error = reason
        project.failures.append({"operation": operation.id, "position": operation.position.to_dict(), "reason": reason})

    async def _install_scaffold(self, operation: BuildOperation, project: ProjectState) -> list[Vec3i]:
        """Build a short verified scaffold column when a placement has no usable interaction face."""
        if operation.position.y <= project.plan.approved_area.minimum.y:
            return []
        base = None
        for distance in range(1, 9):
            candidate = operation.position.offset(dy=-distance)
            if not project.plan.approved_area.contains(candidate):
                break
            if await self.port.block_at(candidate) != "minecraft:air":
                base = candidate
                break
        if base is None:
            return []
        placed: list[Vec3i] = []
        for y in range(base.y + 1, operation.position.y):
            position = Vec3i(operation.position.x, y, operation.position.z)
            if await self.port.block_at(position) != "minecraft:air":
                continue
            scaffold = BuildOperation(OperationKind.PLACE, position, "minecraft:scaffolding",
                                      "_temporary_scaffold", temporary=True)
            if not await self._gate(project):
                break
            options = candidates(scaffold, await self.port.interaction_world(scaffold.position))
            if not options:
                break
            nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION, options[0].feet, .75),
                                      await self.port.world_state(), project)
            if not nav.success or not await self._gate(project):
                break
            self._remember_temporary(project, scaffold)
            if not await self.port.place_block(scaffold) or not await self._already_satisfied(scaffold):
                break
            placed.append(position)
            if self.checkpoint:
                self.checkpoint(project)
        if placed:
            project.modifications.append(f"temporary scaffold installed for {operation.id}")
            LOG.info("temporary scaffold installed", extra={"blocks": len(placed), "operation_id": operation.id})
        return placed

    async def _install_access(self, operation: BuildOperation, project: ProjectState) -> None:
        """Bounded stair-step ramp plus a short platform; no global scaffold planner."""
        target = operation.position
        height = target.y - project.design.origin.y
        if not 1 <= height <= 10:
            return
        area = project.plan.temporary_area or project.plan.approved_area
        # Ramp stays outside the western wall, ending beside the operation's row.
        top = Vec3i(project.design.origin.x - 2, target.y - 1, target.z)
        # A diagonal list alone is not placeable through a player: consecutive
        # cells touch only at an edge. Fill each stair column from known ground
        # so every new block has an adjacent support face.
        positions = [Vec3i(top.x-height+i, y, top.z) for i in range(height+1)
                     for y in range(project.design.origin.y-1, top.y-height+i+1)]
        # Connect the outside ramp to the floor: without this cell a two-block
        # elevation leaves a one-cell gap that requires disabled parkour.
        positions += [top.offset(dx=1)]
        # A short platform allows a reachable horizontal interaction without entering the target.
        positions += [top.offset(dz=delta) for delta in (-1, 1)]
        final_positions = {op.position for op in project.plan.operations if op.kind == OperationKind.PLACE}
        for point in positions:
            if not area.contains(point) or point in final_positions or not await self._gate(project):
                return
            if await self.port.block_at(point) not in AIR:
                continue
            scaffold = BuildOperation(OperationKind.PLACE, point, "minecraft:cobblestone", "_temporary_access", temporary=True)
            options = candidates(scaffold, await self.port.interaction_world(scaffold.position))
            if not options:
                return
            nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION, options[0].feet, .75),
                                      await self.port.world_state(), project)
            if not nav.success or not await self._gate(project):
                return
            self._remember_temporary(project, scaffold)
            if not await self.port.place_block(scaffold) or not await self._already_satisfied(scaffold):
                return
            if self.checkpoint:
                self.checkpoint(project)
        project.modifications.append(f"temporary access ramp/platform for {operation.id}")

    @staticmethod
    def _construction_feet_allowed(operation, feet, project):
        """House phase access constraint, not a general sole-exit proof.

        Closing facades is exterior work; an upper slab cannot be built from
        the enclosed lower floor merely because the ray is within reach.
        """
        if operation.temporary: return True
        component = next((c for c in project.design.components if c.id == operation.component_id),None)
        if component and component.metadata.get("exterior_access"):
            # An open floor can be assembled from ABOVE before its walls exist.
            # Closing walls never inherit this exception; their next mutation
            # requires actual exterior arrival. Under-floor approaches stay banned.
            if component.metadata.get("open_top_access") and feet.y > component.bounds.maximum.y:
                return True
            volume = component.metadata.get("exterior_volume")
            area = Bounds(Vec3i(**volume['minimum']),Vec3i(**volume['maximum'])) if volume else component.bounds
            return not (area.minimum.x <= feet.x <= area.maximum.x and area.minimum.z <= feet.z <= area.maximum.z
                        and feet.y <= area.maximum.y)
        name = zone_id(operation)
        origin = project.design.origin
        if name.startswith("floor_") and "." in name:
            floor = int(name.split(".")[0].removeprefix("floor_"))
            if ".wall_" in name:
                outside = not (origin.x <= feet.x < origin.x+project.design.parameters["width"]
                               and origin.z <= feet.z < origin.z+project.design.parameters["depth"])
                return outside and (floor == 1 or feet.y >= origin.y+3+(floor-1)*project.design.parameters["floor_height"])
            if name.endswith(".slab") and floor >= 2:
                return feet.y >= origin.y+(floor-1)*project.design.parameters["floor_height"]+1
        if name == "roof": return feet.y >= operation.position.y+1
        return True

    async def _prepare_zone_access(self, operation, project):
        """One shared exterior stair/ring per facade phase, retained until cleanup.

        A raised ring provides work access and an exit when the facade closes.
        It is not rebuilt for each window and never occupies permanent geometry.
        """
        if self.config.creative_flight:
            world = await self.port.world_state()
            if world.player.creative and world.player.flying:
                return  # Actual observed flight replaces ground access, not a config assertion.
        name = zone_id(operation)
        if name == "roof":
            level = project.design.origin.y + project.design.parameters["floors"]*project.design.parameters["floor_height"] + 1
        elif name.startswith("floor_") and ".wall_" in name:
            floor = int(name.split(".")[0].removeprefix("floor_"))
            level = project.design.origin.y + 2 + (floor-1)*project.design.parameters["floor_height"]
        elif name.startswith("floor_") and name.endswith(".slab"):
            floor = int(name.split(".")[0].removeprefix("floor_"))
            if floor < 2: return
            level = project.design.origin.y + (floor-1)*project.design.parameters["floor_height"]
        else: return
        if level in self._access_levels: return
        origin = project.design.origin
        width, depth = project.design.parameters["width"], project.design.parameters["depth"]
        # Distinct approach lanes retain the lower floor's exit while extending
        # a higher stair; raising one shared column would erase that exit.
        lane = min(len(self._access_levels)*3, depth-1)
        top = Vec3i(origin.x-2, level, origin.z+lane)
        height = level-origin.y+1
        positions = [Vec3i(top.x-height+i, y, top.z) for i in range(height+1)
                     for y in range(origin.y-1, top.y-height+i+1)]
        if name == "roof":
            # Build the bridge bottom-up so the first roof edge is accessible
            # before any permanent roof cell exists.
            positions += [Vec3i(top.x+1,y,top.z) for y in range(origin.y-1,level+1)]
        else:
            positions.append(top.offset(dx=1))
        # Connected perimeter, including outside corners. Each next cell has an
        # already placed adjacent face or a verified slab face.
        if ".wall_" in name or name == "roof" or name.endswith(".slab"):
            positions += [Vec3i(origin.x-1,level,z) for z in range(top.z,origin.z+depth+1)]
            positions += [Vec3i(x,level,origin.z+depth) for x in range(origin.x,origin.x+width+1)]
            positions += [Vec3i(origin.x+width,level,z) for z in range(origin.z+depth-1,origin.z-2,-1)]
            positions += [Vec3i(x,level,origin.z-1) for x in range(origin.x+width-1,origin.x-2,-1)]
            positions += [Vec3i(origin.x-1,level,z) for z in range(origin.z,top.z)]
        else:
            positions += [top.offset(dz=-1), top.offset(dz=1)]
        final = {op.position for op in project.plan.operations}
        area = project.plan.temporary_area or project.plan.approved_area
        if any(not area.contains(p) or p in final for p in positions):
            LOG.warning("ACCESS planned ring exceeds permitted temporary space"); return
        async def enter_landing():
            world = await self.port.world_state()
            nav = await self._navigate(NavigationGoal(NavigationGoalKind.RETURN_TO,top.offset(dy=1),.75),world,project)
            if not nav.success: LOG.warning("ACCESS cannot enter verified landing: %s",nav.reason)
            return nav.success
        for point in dict.fromkeys(positions):
            if not await self._gate(project): return
            actual = await self.port.block_at(point)
            owned = any(Vec3i(**entry["position"]) == point for entry in project.temporary_blocks)
            if actual not in AIR:
                if point.y < origin.y and actual not in ("minecraft:water", "minecraft:lava", "minecraft:fire", "minecraft:magma_block"):
                    continue  # Existing ground supports the stair; never journal it as owned.
                if not owned:
                    LOG.warning("ACCESS existing obstacle at %s; no unauthorized clearing", point); return
                if point == top.offset(dx=1) and not await enter_landing(): return
                continue
            scaffold = BuildOperation(OperationKind.PLACE, point, "minecraft:cobblestone", "_temporary_access", temporary=True)
            failed_feet = set()
            for attempt in range(self.max_attempts):
                if await self._already_satisfied(scaffold): break
                world = await self.port.interaction_world(point)
                options = [candidate for candidate in candidates(scaffold, world, reach=self.config.placement_radius)
                           if candidate.feet not in failed_feet]
                current = world.player.position not in failed_feet and can_interact(scaffold, world, world.player.position, self.config.placement_radius)
                if not current:
                    if not options:
                        LOG.warning("ACCESS no safe placement face at %s", point); return
                    spot = options[0].feet
                    nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION, spot, .75), world, project)
                    if not nav.success:
                        failed_feet.add(spot)
                        LOG.warning("ACCESS navigation failed at %s: %s", point, nav.reason)
                        continue
                if not await self._gate(project): return
                self._remember_temporary(project, scaffold)
                await self.port.place_block(scaffold)
                if await self._already_satisfied(scaffold): break
                failed_feet.add((await self.port.world_state()).player.position)
                LOG.warning("ACCESS placement rejected point=%s attempt=%s reason=%s", point, attempt+1,
                    getattr(self.port,"last_action_reason","") or "observed state mismatch")
            else:
                LOG.warning("ACCESS exhausted bounded alternatives at %s", point); return
            if point == top.offset(dx=1) and not await enter_landing(): return
        # Extending a side face can require a lower observation/interaction
        # position. Re-enter the FINISHED ring before any permanent work.
        if not await enter_landing(): return
        self._access_levels.add(level)
        project.scheduler.setdefault("access_levels", []).append(level)
        project.scheduler.setdefault("access_landings", []).append(top.offset(dy=1).to_dict())
        project.modifications.append(f"shared upper-floor stair and perimeter platform at y={level}")
        LOG.info("ACCESS ready level=%s shared_blocks=%s", level, len(set(positions)))

    def _remember_temporary(self, project: ProjectState, operation: BuildOperation) -> None:
        # Journal an intended temporary mutation before sending it: disconnect can hide its outcome.
        if not any(Vec3i(**entry["position"]) == operation.position for entry in project.temporary_blocks):
            project.temporary_blocks.append({"position": operation.position.to_dict(), "block": operation.block})
        if self.checkpoint:
            self.checkpoint(project)

    async def _safe_cleanup(self, project):
        if not project.temporary_blocks: return
        landings = project.scheduler.get("access_landings", [])
        reached = not landings
        for entry in reversed(landings[-3:]):
            anchor = Vec3i(**entry)
            if await self.port.block_at(anchor.offset(dy=-1)) != "minecraft:cobblestone": continue
            world = await self.port.world_state()
            nav = await self._navigate(NavigationGoal(NavigationGoalKind.RETURN_TO,anchor,.75),world,project)
            if nav.success:
                reached = True
                break
        if not reached and project.design.bounds.contains((await self.port.world_state()).player.position):
            project.scheduler["cleanup_deferred"] = "safe outside landing unreachable; do not dismantle access while enclosed"
            self.metrics.counts["cleanup_refused_unsafe_retreat"] += 1
            LOG.warning("CLEANUP deferred: safe outside retreat was not reached")
            return
        project.scheduler.pop("cleanup_deferred",None)
        await self._remove_scaffold([Vec3i(**entry["position"]) for entry in list(project.temporary_blocks)],project)

    async def _remove_scaffold(self, positions: list[Vec3i], project: ProjectState) -> None:
        for position in reversed(positions):
            if not await self._gate(project):
                return
            removal = BuildOperation(OperationKind.BREAK, position, None, "_temporary_scaffold",
                                     destructive=True, temporary=True)
            if (project.plan.temporary_area or project.plan.approved_area).contains(position):
                LOG.info("destructive operation", extra={"position": position.to_dict(), "temporary": True})
                owned = next((e for e in project.temporary_blocks if Vec3i(**e["position"]) == position), None)
                if owned is None:
                    continue
                actual = await self.port.block_at(position)
                if actual in AIR:
                    project.temporary_blocks.remove(owned)
                    continue
                if actual != owned["block"]:
                    continue
                for attempt in range(self.max_attempts):
                    world = await self.port.interaction_world(removal.position)
                    options = candidates(removal, world)
                    if not options: break
                    if can_interact(removal, world, world.player.position, self.config.placement_radius):
                        from .navigation import NavigationResult
                        nav = NavigationResult(True,world.player.position,"reuse cleanup position")
                    else:
                        nav = await self._navigate(NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION,
                            options[min(attempt, len(options)-1)].feet, .75), world, project)
                    if not await self._gate(project): return
                    if nav.success:
                        await self.port.break_block(removal)
                        if await self.port.block_at(position) in AIR:
                            project.temporary_blocks.remove(owned)
                            break


class Validator:
    async def validate(self, project: ProjectState, port: MinecraftPort) -> ValidationReport:
        if project.dimension and (await port.world_state()).player.dimension != project.dimension:
            raise RuntimeError("cannot validate a project in another dimension")
        scanned = await port.scan_region(project.plan.temporary_area or project.plan.approved_area)
        correct = missing = incorrect = 0
        mismatch_ids = []
        for operation in project.plan.operations:
            if operation.kind != OperationKind.PLACE:
                continue
            actual, properties = scanned.get(operation.position, ("minecraft:air", {})) if scanned is not None else await port.inspect_block(operation.position)
            if actual == operation.block and all(properties.get(k) == v for k, v in operation.properties.items()):
                correct += 1
            elif actual == "minecraft:air":
                missing += 1
                mismatch_ids.append(operation.id)
            else:
                incorrect += 1
                mismatch_ids.append(operation.id)
        # Intent journal length is not a world count: a rejected/interrupted
        # placement may never have created the block. Retain occupied conflicts
        # conservatively, but reconcile observed air before final reporting.
        for entry in list(project.temporary_blocks):
            point = Vec3i(**entry["position"])
            actual = scanned.get(point, ("minecraft:air", {}))[0] if scanned is not None else await port.block_at(point)
            if actual in AIR:
                project.temporary_blocks.remove(entry)
        extra = 0
        if scanned is not None:
            expected = {op.position for op in project.plan.operations if op.kind == OperationKind.PLACE}
            baseline = {Vec3i(**e["position"]): e["block"] for e in project.baseline}
            temporary = {Vec3i(**e["position"]) for e in project.temporary_blocks}
            # A natural grass→dirt transition under a new floor is not an extra placed block.
            extras = [(pos, block) for pos, (block, _) in scanned.items() if pos not in expected and pos not in temporary
                      and block not in AIR and baseline.get(pos, "minecraft:air") in AIR]
            extra = len(extras)
        report = ValidationReport(correct + missing + incorrect, correct, missing, incorrect, extra, len(project.temporary_blocks))
        project.validation = report.__dict__.copy() | {"verified": report.verified}
        project.validation["mismatch_operation_ids"] = mismatch_ids
        if scanned is not None:
            project.validation["extra_details"] = [{"position": p.to_dict(), "block": block} for p, block in extras[:256]]
            project.validation["baseline_change_details"] = [{"position": p.to_dict(), "before": baseline[p], "after": block}
                for p, (block, _) in scanned.items() if p not in expected and p in baseline and block != baseline[p]][:256]
        return report


class ProjectStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, project: ProjectState) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{project.id}.json"
        staging = target.with_suffix(".json.tmp")
        with staging.open("w", encoding="utf-8") as stream:
            json.dump(project.to_dict(), stream, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers/antivirus can briefly hold the old file without
        # FILE_SHARE_DELETE. Keep the previous checkpoint intact and retry only
        # this atomic rename, never replay an in-world mutation.
        for attempt in range(6):
            try:
                os.replace(staging, target)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                sleep(.02 * (2 ** attempt))
        return target

    def load(self, path: Path) -> ProjectState:
        from .models import Design, BuildPlan, StructureComponent
        value = json.loads(path.read_text(encoding="utf-8"))
        def bounds(data):
            return Bounds(Vec3i(**data["minimum"]), Vec3i(**data["maximum"]))
        data = value["design"]
        design = Design(data["name"], Vec3i(**data["origin"]), bounds(data["bounds"]),
            [StructureComponent(**(c | {"bounds": bounds(c["bounds"])})) for c in data["components"]], data["parameters"])
        data = value["plan"]
        operations = [BuildOperation(**(o | {"kind": OperationKind(o["kind"]), "status": OperationStatus(o["status"]),
                                             "position": Vec3i(**o["position"])})) for o in data["operations"]]
        plan = BuildPlan(design, operations, data["materials"], bounds(data["approved_area"]),
                         bounds(data["temporary_area"]) if data.get("temporary_area") else None)
        return ProjectState(**(value | {"design": design, "plan": plan, "status": ProjectStatus(value["status"])}))


class BlockMindAgent:
    def __init__(self, port: MinecraftPort, navigation: NavigationProvider, intent: IntentProvider | None = None, config: ExecutionConfig | None = None) -> None:
        self.port = port
        self.navigation = navigation
        self.control = ControlState()
        self.port.control_state = self.control
        self.intent = intent or PromptInterpreter()
        self.config = config or ExecutionConfig()

    def plan(self, request: str, origin: Vec3i) -> ProjectState:
        spec = self.intent.interpret(request)
        design = ModernHouseArchitect().create_design(spec, origin)
        LOG.info("design created", extra={"category": "ARCHITECT", "blocks": design.bounds.to_dict()})
        plan = ModernHouseGeometry().generate(design)
        LOG.info("build plan generated", extra={"category": "PLANNER", "blocks": len(plan.operations)})
        return ProjectState(request, design, plan)

    async def run(self, request: str, origin: Vec3i,
                  on_progress: Callable[[ProjectState, BuildOperation], None] | None = None,
                  store: ProjectStore | None = None) -> tuple[ProjectState, ValidationReport]:
        project = self.plan(request, origin)
        return await self.run_project(project, on_progress, store)

    async def run_project(self, project: ProjectState, on_progress=None, store: ProjectStore | None = None,
                          reconcile: bool = False) -> tuple[ProjectState, ValidationReport]:
        self.project = project
        run_started = perf_counter()
        world = await self.port.world_state()
        if project.dimension and project.dimension != world.player.dimension:
            raise RuntimeError("project belongs to a different dimension")
        project.dimension = world.player.dimension
        await self.port.approve(project)
        before_audio = None
        server = getattr(self.port, "server", None)
        if server and server.metadata and "PERFORMANCE_METRICS" in server.metadata.capabilities:
            before_audio = await server.request("performance", {})
            for _ in range(5):
                await server.request("ping", {})
        project.execution = self.config.to_dict()
        builder = Builder(self.port, self.navigation, self.control, config=self.config)
        builder.legacy_scheduler = getattr(self, "legacy_scheduler", False)
        self.builder = builder
        builder.checkpoint = store.save if store else None
        if not reconcile:
            baseline = await self.port.scan_region(project.plan.temporary_area or project.plan.approved_area)
            if baseline is not None:
                project.baseline = [{"position": p.to_dict(), "block": block} for p, (block, _) in baseline.items() if block not in AIR]
                project.baseline_captured = True
        try:
            await self.port.configure_execution(self.config)
            if reconcile:
                await builder.reconcile(project)
            if store:
                store.save(project)
            await builder.execute(project, on_progress)
            if self.control.stopped:
                expected = sum(op.kind == OperationKind.PLACE for op in project.plan.operations)
                report = ValidationReport(expected, 0, expected, 0, temporary_remaining=len(project.temporary_blocks))
                project.validation = report.__dict__ | {"verified": False, "reason": "stopped; final scan not performed"}
            else:
                with builder.metrics.measure("final_verification"):
                    report = await Validator().validate(project, self.port)
                if (report.missing or report.incorrect) and project.scheduler.get("cleanup_deferred"):
                    builder.metrics.counts["final_repair_refused_unsafe_retreat"] += 1
                    LOG.warning("final repair refused: unsafe retreat unresolved; preserve final failed scan")
                elif report.missing or report.incorrect:
                    mismatches = set(project.validation.get("mismatch_operation_ids", []))
                    # One bounded strict repair pass, never an infinite retry/rebuild loop.
                    repairs = [op for op in builder._ordered or project.plan.operations if op.id in mismatches][:256]
                    for op in repairs:
                        op.status = OperationStatus.PENDING
                        project.completed_operation_ids[:] = [value for value in project.completed_operation_ids if value != op.id]
                    builder.metrics.counts["final_repair_operations"] += len(repairs)
                    LOG.warning("final validation requires bounded repair", extra={"blocks": len(repairs)})
                    await builder._execute_strict(project, on_progress, repairs)
                    if not self.control.stopped:
                        with builder.metrics.measure("final_verification"):
                            report = await Validator().validate(project, self.port)
                    else:
                        project.validation["verified"] = False
                        project.validation["reason"] = "stopped during final repair; final scan not performed"
            if report.verified and not self.control.stopped and not project.failures:
                project.status = ProjectStatus.COMPLETE
            if not report.verified and project.status == ProjectStatus.COMPLETE:
                project.status = ProjectStatus.FAILED
        except ExecutionStopped:
            if not self.control.stopped:
                raise
            project.status = ProjectStatus.STOPPED
            expected = sum(op.kind == OperationKind.PLACE for op in project.plan.operations)
            report = ValidationReport(expected,0,expected,0,temporary_remaining=len(project.temporary_blocks))
            project.validation = report.__dict__ | {"verified":False,"reason":"stopped; final scan not performed"}
        except BaseException:
            project.status = ProjectStatus.STOPPED if self.control.stopped else ProjectStatus.FAILED
            raise
        finally:
            project.performance = builder.metrics.snapshot()
            positions = {builder._placed_at[identifier] for identifier in builder._placed_ids if identifier in builder._placed_at}
            project.performance["interaction_position_count"] = len(positions)
            project.performance["operations_per_interaction_position"] = len(builder._placed_ids)/len(positions) if positions else None
            project.performance["total_run_seconds"] = perf_counter() - run_started
            if before_audio: project.performance["before_configuration"] = before_audio
            server = getattr(self.port, "server", None)
            if server:
                project.performance["transport"] = server.metrics.snapshot()
            try:
                if server and server.metadata and "PERFORMANCE_METRICS" in server.metadata.capabilities:
                    project.performance["adapter"] = await server.request("performance", {})
                    adapter = project.performance["adapter"]
                    nav_before = (before_audio or {}).get("navigationTimings", {})
                    nav_after = adapter.get("navigationTimings", {})
                    route = {"travel_distance_blocks": counter_delta((before_audio or {}).get("runtimeState", {}), adapter.get("runtimeState", {}), "travelDistanceBlocks"),
                        "baritone_goals": counter_delta(nav_before, nav_after, "baritoneGoals"),
                        "local_movements": counter_delta(nav_before, nav_after, "localGoals"),
                        "flight_goals": counter_delta(nav_before, nav_after, "flightGoals"),
                        "flight_active_seconds": counter_delta(nav_before, nav_after, "flightActiveSeconds"),
                        "rotations": counter_delta((before_audio or {}).get("gameTimings", {}), adapter.get("gameTimings", {}), "rotations"),
                        "material_switches": counter_delta((before_audio or {}).get("gameTimings", {}), adapter.get("gameTimings", {}), "selections")}
                    route["adapter_counters_verified"] = all(value is not None for value in route.values())
                    route.update({key: builder.metrics.counts[key] for key in ("navigation_requests","region_switches","component_switches","backtracks")})
                    route["core_navigation_calls"] = route["navigation_requests"]
                    route["navigation_requests"] = server.metrics.counts["request.navigate"]
                    route["elevation_changes"] = counter_delta((before_audio or {}).get("runtimeState", {}), adapter.get("runtimeState", {}), "elevationChanges")
                    route["operations_per_navigation_goal"] = len(builder._placed_ids)/route["navigation_requests"] if route["navigation_requests"] else None
                    project.performance["movement"] = route
                await self.port.finish_execution()
                if server and server.metadata and "PERFORMANCE_METRICS" in server.metadata.capabilities:
                    project.performance["after_finish"] = await server.request("performance", {})
            except (ConnectionError, RuntimeError, asyncio.TimeoutError):
                pass
            # Include finish/audio restoration and final diagnostic requests.
            # This is still Core time, not launcher/client teardown time.
            project.performance['total_run_seconds'] = perf_counter()-run_started
            if server:
                project.performance['transport'] = server.metrics.snapshot()
            if store:
                store.save(project)
        LOG.info("build validation complete", extra={"category": "QA", "blocks": report.__dict__})
        return project, report

    def pause(self) -> None:
        self.control.pause()

    def resume(self) -> None:
        self.control.resume()

    async def stop(self) -> None:
        self.control.stop()
        await self.port.control("stop")
        await self.navigation.cancel()

    async def emergency_stop(self) -> None:
        self.control.stop()
        await self.port.control("emergency_stop")
        await self.navigation.cancel()

    async def send_control(self, kind: str) -> None:
        if kind == "pause":
            self.pause()
            await self.port.control(kind)
            await self.navigation.cancel()
        elif kind == "resume":
            await self.port.control(kind)
            self.resume()
        elif kind == "stop":
            await self.stop()
        elif kind == "emergency_stop":
            await self.emergency_stop()
        else:
            raise ValueError(f"unknown control: {kind}")

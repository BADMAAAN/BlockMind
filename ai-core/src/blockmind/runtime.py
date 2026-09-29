from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .design import ModernHouseArchitect, PromptInterpreter
from .geometry import ModernHouseGeometry
from .models import (Bounds, BuildOperation, OperationKind, OperationStatus, ProjectState,
                     ProjectStatus, Vec3i, WorldState)
from .navigation import NavigationGoal, NavigationGoalKind, NavigationProvider

LOG = logging.getLogger("blockmind")


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

    @property
    def verified(self) -> bool:
        return self.expected == self.correct and self.missing == 0 and self.incorrect == 0


class Builder:
    def __init__(self, port: MinecraftPort, navigation: NavigationProvider,
                 control: ControlState | None = None, max_attempts: int = 3) -> None:
        self.port = port
        self.navigation = navigation
        self.control = control or ControlState()
        self.max_attempts = max_attempts

    async def execute(self, project: ProjectState,
                      on_progress: Callable[[ProjectState, BuildOperation], None] | None = None) -> ProjectState:
        project.status = ProjectStatus.BUILDING
        for operation in project.plan.operations:
            await self.control.wait()
            if self.control.stopped:
                project.status = ProjectStatus.STOPPED
                await self.navigation.cancel()
                return project
            if operation.destructive and not project.plan.approved_area.contains(operation.position):
                operation.status = OperationStatus.FAILED
                operation.error = "destructive operation outside approved area"
                project.failures.append({"operation": operation.id, "reason": operation.error})
                project.status = ProjectStatus.FAILED
                return project
            if await self._already_satisfied(operation):
                operation.status = OperationStatus.COMPLETE
                project.completed_operation_ids.append(operation.id)
                continue

            world = await self.port.world_state()
            approach = self._approach_position(operation.position, world)
            nav = await self.navigation.navigate(
                NavigationGoal(NavigationGoalKind.MOVE_TO_BUILD_POSITION, approach), world)
            if not nav.success:
                self._fail(project, operation, f"navigation: {nav.reason}")
                continue

            operation.status = OperationStatus.RUNNING
            temporary_scaffold: list[Vec3i] = []
            for _ in range(self.max_attempts):
                operation.attempts += 1
                acted = await (self.port.place_block(operation) if operation.kind == OperationKind.PLACE
                               else self.port.break_block(operation))
                if acted and await self._already_satisfied(operation):
                    operation.status = OperationStatus.COMPLETE
                    project.completed_operation_ids.append(operation.id)
                    break
                if operation.kind == OperationKind.PLACE and not temporary_scaffold:
                    temporary_scaffold = await self._install_scaffold(operation, project)
                LOG.warning("action verification failed", extra={"operation_id": operation.id, "attempt": operation.attempts})
            else:
                self._fail(project, operation, "verification failed after retries")
            if temporary_scaffold:
                await self._remove_scaffold(temporary_scaffold, project)
            if on_progress:
                on_progress(project, operation)

        project.status = ProjectStatus.COMPLETE if not project.failures else ProjectStatus.FAILED
        return project

    async def _already_satisfied(self, operation: BuildOperation) -> bool:
        actual = await self.port.block_at(operation.position)
        if operation.kind == OperationKind.BREAK:
            return actual == "minecraft:air"
        return actual == operation.block

    @staticmethod
    def _approach_position(target: Vec3i, world: WorldState) -> Vec3i:
        candidates = [target.offset(dx=-1), target.offset(dx=1), target.offset(dz=-1), target.offset(dz=1)]
        candidates.sort(key=lambda p: p.distance_squared(world.player.position))
        return next((p for p in candidates if not world.is_hazardous(p)), candidates[0])

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
            if not await self.port.place_block(scaffold) or not await self._already_satisfied(scaffold):
                break
            placed.append(position)
        if placed:
            project.modifications.append(f"temporary scaffold installed for {operation.id}")
            LOG.info("temporary scaffold installed", extra={"blocks": len(placed), "operation_id": operation.id})
        return placed

    async def _remove_scaffold(self, positions: list[Vec3i], project: ProjectState) -> None:
        for position in reversed(positions):
            removal = BuildOperation(OperationKind.BREAK, position, None, "_temporary_scaffold",
                                     destructive=True, temporary=True)
            if project.plan.approved_area.contains(position):
                LOG.info("destructive operation", extra={"position": position.to_dict(), "temporary": True})
                await self.port.break_block(removal)


class Validator:
    async def validate(self, project: ProjectState, port: MinecraftPort) -> ValidationReport:
        correct = missing = incorrect = 0
        for operation in project.plan.operations:
            if operation.kind != OperationKind.PLACE:
                continue
            actual = await port.block_at(operation.position)
            if actual == operation.block:
                correct += 1
            elif actual == "minecraft:air":
                missing += 1
            else:
                incorrect += 1
        report = ValidationReport(correct + missing + incorrect, correct, missing, incorrect)
        project.validation = report.__dict__.copy() | {"verified": report.verified}
        return report


class ProjectStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, project: ProjectState) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{project.id}.json"
        target.write_text(json.dumps(project.to_dict(), indent=2, default=str), encoding="utf-8")
        return target


class BlockMindAgent:
    def __init__(self, port: MinecraftPort, navigation: NavigationProvider) -> None:
        self.port = port
        self.navigation = navigation
        self.control = ControlState()

    def plan(self, request: str, origin: Vec3i) -> ProjectState:
        spec = PromptInterpreter().interpret(request)
        design = ModernHouseArchitect().create_design(spec, origin)
        LOG.info("design created", extra={"category": "ARCHITECT", "blocks": design.bounds.to_dict()})
        plan = ModernHouseGeometry().generate(design)
        LOG.info("build plan generated", extra={"category": "PLANNER", "blocks": len(plan.operations)})
        return ProjectState(request, design, plan)

    async def run(self, request: str, origin: Vec3i,
                  on_progress: Callable[[ProjectState, BuildOperation], None] | None = None) -> tuple[ProjectState, ValidationReport]:
        project = self.plan(request, origin)
        await Builder(self.port, self.navigation, self.control).execute(project, on_progress)
        report = await Validator().validate(project, self.port)
        LOG.info("build validation complete", extra={"category": "QA", "blocks": report.__dict__})
        if not report.verified and project.status == ProjectStatus.COMPLETE:
            project.status = ProjectStatus.FAILED
        return project, report

    def pause(self) -> None:
        self.control.pause()

    def resume(self) -> None:
        self.control.resume()

    async def stop(self) -> None:
        self.control.stop()
        await self.navigation.cancel()

    async def emergency_stop(self) -> None:
        self.control.stop()
        await self.navigation.cancel()

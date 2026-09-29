from __future__ import annotations

from .models import BuildOperation, OperationKind, PlayerState, Vec3i, WorldState
from .runtime import MinecraftPort


class SimulatedMinecraftPort(MinecraftPort):
    """In-memory adapter for end-to-end tests; it does not claim to simulate Minecraft physics."""

    def __init__(self, origin: Vec3i = Vec3i(0, 64, 0), fail_first_attempt: set[Vec3i] | None = None) -> None:
        self.world = WorldState(PlayerState(origin))
        self.fail_first_attempt = fail_first_attempt or set()
        self.attempts: dict[Vec3i, int] = {}

    async def world_state(self) -> WorldState:
        return self.world

    async def place_block(self, operation: BuildOperation) -> bool:
        count = self.attempts.get(operation.position, 0) + 1
        self.attempts[operation.position] = count
        if operation.position in self.fail_first_attempt and count == 1:
            return False
        if operation.block is None:
            return False
        self.world.blocks[operation.position] = operation.block
        return True

    async def break_block(self, operation: BuildOperation) -> bool:
        self.world.blocks.pop(operation.position, None)
        return True

    async def block_at(self, position: Vec3i) -> str:
        return self.world.block_at(position)

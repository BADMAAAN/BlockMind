from __future__ import annotations

import asyncio
import logging
from typing import Any

from .models import Bounds, BuildOperation, Hazard, HazardKind, PlayerState, Vec3i, WorldState
from .navigation import NavigationGoal, NavigationProvider, NavigationResult
from .protocol import Envelope, NdjsonSession
from .runtime import MinecraftPort

LOG = logging.getLogger("blockmind.network")


class FabricSessionServer:
    """Single-client local transport. Bind externally only behind authentication."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host, self.port = host, port
        self.session: NdjsonSession | None = None
        self.observation = WorldState(PlayerState(Vec3i(0, 0, 0)))
        self._connected = asyncio.Event()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._accept, self.host, self.port)
        LOG.info("waiting for Fabric adapter at %s:%s", self.host, self.port)

    async def wait_connected(self, timeout: float = 120.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self.session is not None:
            writer.close()
            return
        self.session = NdjsonSession(reader, writer)
        self._connected.set()
        LOG.info("Fabric adapter connected")
        try:
            while True:
                message = await self.session.receive()
                if message.type == "observation":
                    self._apply_observation(message.payload)
                elif message.type == "action_result":
                    future = self._pending.pop(message.id, None)
                    if future and not future.done():
                        future.set_result(message.payload)
        except (EOFError, ConnectionError):
            LOG.warning("Fabric adapter disconnected")
        finally:
            self.session = None
            self._connected.clear()

    def _apply_observation(self, payload: dict[str, Any]) -> None:
        player = payload.get("player", {})
        position = player.get("position", {})
        self.observation.player = PlayerState(
            Vec3i(int(position.get("x", 0)), int(position.get("y", 0)), int(position.get("z", 0))),
            dimension=player.get("dimension", "minecraft:overworld"),
            health=float(player.get("health", 20)),
            hunger=int(player.get("hunger", 20)),
            creative=bool(player.get("creative", False)),
            on_ground=bool(player.get("onGround", False)),
            inventory={entry["item"]: int(entry.get("count", 0)) for entry in player.get("inventory", [])},
        )
        radius = int(payload.get("radius", 0))
        if radius:
            bounds = Bounds(self.observation.player.position.offset(-radius, -radius, -radius),
                            self.observation.player.position.offset(radius, radius, radius))
            self.observation.observed_bounds = bounds
            self.observation.blocks = {pos: block for pos, block in self.observation.blocks.items()
                                       if not bounds.contains(pos)}
        for entry in payload.get("blocks", []):
            pos = entry["position"]
            self.observation.blocks[Vec3i(pos["x"], pos["y"], pos["z"])] = entry["block"]
        hazards: list[Hazard] = []
        for entry in payload.get("hazards", []):
            pos = entry["position"]
            point = Vec3i(pos["x"], pos["y"], pos["z"])
            try:
                kind = HazardKind(entry["kind"])
            except ValueError:
                continue
            hazards.append(Hazard(kind, Bounds(point, point), float(entry.get("severity", 1.0))))
        self.observation.hazards = hazards

    async def request(self, kind: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        if not self.session:
            raise ConnectionError("Fabric adapter is not connected")
        message = Envelope("action", {"kind": kind} | payload)
        encoded_id = message.id = __import__("uuid").uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[encoded_id] = future
        await self.session.send(message)
        return await asyncio.wait_for(future, timeout)

    async def close(self) -> None:
        if self.session:
            self.session.writer.close()
            await self.session.writer.wait_closed()
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class FabricMinecraftPort(MinecraftPort):
    def __init__(self, server: FabricSessionServer) -> None:
        self.server = server

    async def world_state(self) -> WorldState:
        return self.server.observation

    async def place_block(self, operation: BuildOperation) -> bool:
        result = await self.server.request("place_block", {
            "position": operation.position.to_dict(), "block": operation.block,
        })
        if result.get("observedBlock"):
            self.server.observation.blocks[operation.position] = result["observedBlock"]
        return bool(result.get("success"))

    async def break_block(self, operation: BuildOperation) -> bool:
        result = await self.server.request("break_block", {"position": operation.position.to_dict()})
        if result.get("success"):
            self.server.observation.blocks[operation.position] = "minecraft:air"
        return bool(result.get("success"))

    async def block_at(self, position: Vec3i) -> str:
        result = await self.server.request("observe_block", {"position": position.to_dict()}, timeout=5.0)
        block = result.get("observedBlock", "minecraft:air")
        self.server.observation.blocks[position] = block
        return block

    async def close(self) -> None:
        await self.server.close()


class RemoteNavigationProvider(NavigationProvider):
    def __init__(self, server: FabricSessionServer) -> None:
        self.server = server

    async def navigate(self, goal: NavigationGoal, world: WorldState) -> NavigationResult:
        response = await self.server.request("navigate", {
            "goal": goal.kind.value,
            "target": goal.target.to_dict(),
            "tolerance": goal.tolerance,
            "avoidHazards": goal.avoid_hazards,
        }, timeout=120.0)
        position_data = response.get("position", goal.target.to_dict())
        return NavigationResult(bool(response.get("success")), Vec3i(**position_data),
                                response.get("reason", ""), bool(response.get("usedAlternative", False)))

    async def cancel(self) -> None:
        await self.server.request("cancel_navigation", {}, timeout=5.0)

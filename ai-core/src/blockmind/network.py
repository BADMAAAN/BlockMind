from __future__ import annotations

import asyncio
import ipaddress
import logging
from dataclasses import replace
from typing import Any

from .models import Bounds, BuildOperation, Hazard, HazardKind, PlayerState, Vec3i, WorldState
from .navigation import NavigationGoal, NavigationProvider, NavigationResult
from .protocol import AdapterMetadata, CapabilityError, Envelope, MAX_MESSAGE_BYTES, NdjsonSession, ProtocolError
from .runtime import MinecraftPort
from .performance import PerformanceMetrics

LOG = logging.getLogger("blockmind.network")
CAPABILITIES = {
    "observe": "OBSERVE_BLOCKS", "observe_block": "OBSERVE_BLOCKS", "observe_positions": "OBSERVE_BLOCKS",
    "observe_region": "OBSERVE_BLOCKS", "place_block": "PLACE_BLOCK", "break_block": "BREAK_BLOCK",
    "interact": "INTERACT", "navigate": "NAVIGATE", "cancel_navigation": "CANCEL_NAVIGATION",
    "look": "LOOK", "select_hotbar": "SELECT_HOTBAR", "provision": "CREATIVE_PROVISION",
    "action_batch": "ACTION_BATCH", "validate_batch": "VALIDATE_BATCH", "configure_execution": "EXECUTION_CONFIG",
}


class FabricSessionServer:
    """One negotiated, loopback-only adapter. Disconnection never replays mutations."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("unauthenticated transport must bind to a loopback IP")
        self.host, self.port = host, port
        self.session: NdjsonSession | None = None
        self.metadata: AdapterMetadata | None = None
        self.observation = WorldState(PlayerState(Vec3i(0, 0, 0)))
        self._connected = asyncio.Event()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._server: asyncio.Server | None = None
        self._clients: set[asyncio.Task] = set()
        self._action_lock = asyncio.Lock()
        self._closed = False
        self.metrics = PerformanceMetrics()

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._accept, self.host, self.port, limit=MAX_MESSAGE_BYTES)
        self.port = self._server.sockets[0].getsockname()[1]
        LOG.info("waiting for Fabric adapter at %s:%s", self.host, self.port)

    async def wait_connected(self, timeout: float = 120.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        self._clients.add(task)
        session = NdjsonSession(reader, writer)
        if self.session is not None or self._closed:
            writer.close()
            await writer.wait_closed()
            self._clients.discard(task)
            return
        # Reserve the slot during handshake; requests still wait for _connected.
        self.session = session
        try:
            hello = await asyncio.wait_for(session.receive(), 10.0)
            if hello.type != "hello":
                raise ProtocolError("first message must be hello")
            self.metadata = AdapterMetadata.parse(hello.payload)
            await session.send(Envelope("hello_ack", {"accepted": True, "protocol": hello.protocol}, hello.id))
            self._connected.set()
            LOG.info("Fabric adapter connected", extra={"mode": "LIVE", "minecraft": self.metadata.minecraft,
                     "adapter": self.metadata.adapter_version, "protocol": hello.protocol,
                     "capabilities": sorted(self.metadata.capabilities)})
            while True:
                message = await session.receive()
                if message.type == "observation":
                    self._apply_observation(message.payload)
                elif message.type == "action_result":
                    future = self._pending.get(message.id)
                    if future and not future.done():
                        future.set_result(message.payload)
                elif message.type == "hello":
                    # Availability can change after a world/provider loads.
                    update = AdapterMetadata.parse(message.payload)
                    if update.minecraft != self.metadata.minecraft:
                        raise ProtocolError("Minecraft version changed during session")
                    self.metadata = update
                    await session.send(Envelope("hello_ack", {"accepted": True}, message.id))
                else:
                    raise ProtocolError(f"unexpected message type: {message.type}")
        except (EOFError, ConnectionError, ValueError, KeyError, TypeError, asyncio.TimeoutError) as exc:
            LOG.warning("adapter connection closed: %s", exc)
            if not writer.is_closing():
                try:
                    await session.send(Envelope("error", {"reason": str(exc)}))
                except ConnectionError:
                    pass
        finally:
            if self.session is session:
                self.session = None
                self.metadata = None
                self._connected.clear()
                self.observation = WorldState(PlayerState(Vec3i(0, 0, 0)))
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(ConnectionError("adapter disconnected; reconcile before resuming"))
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
            self._clients.discard(task)

    def _apply_observation(self, payload: dict[str, Any]) -> None:
        player = payload.get("player")
        if player:
            inventory: dict[str, int] = {}
            for entry in player.get("inventory", []):
                inventory[entry["item"]] = inventory.get(entry["item"], 0) + int(entry.get("count", 0))
            previous_dimension = self.observation.player.dimension
            self.observation.player = PlayerState(Vec3i(**player["position"]),
                dimension=player.get("dimension", "minecraft:overworld"), health=float(player.get("health", 20)),
                hunger=int(player.get("hunger", 20)), creative=bool(player.get("creative", False)),
                on_ground=bool(player.get("onGround", False)), inventory=inventory,
                velocity=tuple(player.get("velocity", (0, 0, 0))))
            if "eye" in player:
                self.observation.player.eye = tuple(float(v) for v in player["eye"])
            if previous_dimension != self.observation.player.dimension:
                self.observation.blocks.clear()
                self.observation.properties.clear()
                self.observation.solid.clear()
                self.observation.replaceable.clear()
        radius = int(payload.get("radius", 0))
        if radius:
            center = self.observation.player.position
            bounds = Bounds(center.offset(-radius, -radius, -radius), center.offset(radius, radius, radius))
            self.observation.observed_bounds = bounds
            for mapping in (self.observation.blocks, self.observation.properties):
                for pos in list(mapping):
                    if bounds.contains(pos):
                        del mapping[pos]
            self.observation.solid = {p for p in self.observation.solid if not bounds.contains(p)}
            self.observation.replaceable = {p for p in self.observation.replaceable if not bounds.contains(p)}
        for entry in payload.get("blocks", []):
            if not entry.get("loaded", True):
                continue
            point = Vec3i(**entry["position"])
            self.observation.blocks[point] = entry["block"]
            self.observation.properties[point] = entry.get("properties", {})
            self.observation.solid.discard(point)
            self.observation.replaceable.discard(point)
            if entry.get("solid"):
                self.observation.solid.add(point)
            if entry.get("replaceable"):
                self.observation.replaceable.add(point)
        if "hazards" in payload:
            self.observation.hazards = []
            for entry in payload["hazards"]:
                try:
                    kind = HazardKind(entry["kind"])
                except ValueError:
                    continue
                point = Vec3i(**entry["position"])
                self.observation.hazards.append(Hazard(kind, Bounds(point, point), float(entry.get("severity", 1))))

    async def request(self, kind: str, payload: dict[str, Any], timeout: float = 30.0,
                      control: bool = False) -> dict[str, Any]:
        if control:
            return await self._request(kind, payload, timeout, True)
        async with self._action_lock:
            return await self._request(kind, payload, timeout, False)

    async def _request(self, kind: str, payload: dict[str, Any], timeout: float, control: bool) -> dict[str, Any]:
        if not self.session or not self._connected.is_set() or self.metadata is None:
            raise ConnectionError("Fabric adapter has not completed handshake")
        if not control and kind in CAPABILITIES:
            self.metadata.require(CAPABILITIES[kind])
        if kind == "navigate" and not self.metadata.navigation.get("available"):
            raise CapabilityError("navigation provider is unavailable; install a compatible provider")
        message = Envelope("control" if control else "action", {"kind": kind} | payload)
        future = asyncio.get_running_loop().create_future()
        self._pending[message.id] = future
        try:
            with self.metrics.measure("request." + kind):
                await self.session.send(message)
                response = await asyncio.wait_for(future, timeout)
            if "observation" in response:
                self._apply_observation(response["observation"])
            return response
        except asyncio.TimeoutError:
            if not control:
                # Unknown mutation outcome: halt adapter; never silently replay.
                try:
                    await self._request("emergency_stop", {}, 2.0, True)
                except (ConnectionError, asyncio.TimeoutError):
                    pass
            raise
        finally:
            self._pending.pop(message.id, None)

    async def close(self) -> None:
        self._closed = True
        if self.session:
            try:
                await self.request("emergency_stop", {}, 2.0, control=True)
            except (ConnectionError, asyncio.TimeoutError):
                pass
            if self.session:
                self.session.writer.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        tasks = list(self._clients)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class FabricMinecraftPort(MinecraftPort):
    def __init__(self, server: FabricSessionServer) -> None:
        self.server = server
        self.last_action_reason = ""

    @property
    def supports_fast(self):
        return self.server.metadata is not None and {"ACTION_BATCH", "VALIDATE_BATCH"} <= self.server.metadata.capabilities

    async def configure_execution(self, config):
        if self.server.metadata and "EXECUTION_CONFIG" in self.server.metadata.capabilities:
            response = await self.server.request("configure_execution", config.to_dict())
            if not response.get("success"):
                raise RuntimeError(response.get("reason", "configuration rejected"))

    async def finish_execution(self):
        if self.server.metadata and "EXECUTION_CONFIG" in self.server.metadata.capabilities:
            await self.server.request("finish_project", {})

    async def place_batch(self, operations):
        response = await self.server.request("action_batch", {"operations": [self._wire(op) for op in operations]})
        self.server.observation.player.position = Vec3i(**response["position"])
        return response.get("results", [])

    @staticmethod
    def _wire(op):
        return {"id": op.id, "position": op.position.to_dict(), "block": op.block, "properties": op.properties}

    async def validate_operations(self, operations):
        mismatches = set()
        for start in range(0, len(operations), 256):
            response = await self.server.request("validate_batch", {"operations": [self._wire(op) for op in operations[start:start + 256]]})
            if not response.get("success"):
                raise RuntimeError(response.get("reason", "component validation rejected"))
            for entry in response["mismatches"]:
                if not entry["observed"].get("loaded"):
                    raise RuntimeError("component contains unloaded terrain")
                mismatches.add(entry["id"])
        return mismatches

    async def world_state(self) -> WorldState:
        response = await self.server.request("observe", {})
        if not response.get("success"):
            raise RuntimeError(response.get("reason", "world unavailable"))
        return self.server.observation

    async def approve(self, project) -> None:
        response = await self.server.request("approve_region", {"region": project.plan.approved_area.to_dict(),
            "temporaryRegion": (project.plan.temporary_area or project.plan.approved_area).to_dict(),
            "dimension": project.dimension})
        if not response.get("success"):
            raise RuntimeError(response.get("reason", "region approval rejected"))

    async def control(self, kind: str) -> None:
        response = await self.server.request(kind, {}, control=True)
        if not response.get("success"):
            raise RuntimeError(response.get("reason", "control rejected"))

    async def place_block(self, operation: BuildOperation) -> bool:
        response = await self.server.request("place_block", {"position": operation.position.to_dict(),
            "block": operation.block, "properties": operation.properties, "temporary": operation.temporary})
        self.last_action_reason = response.get("reason", "")
        return bool(response.get("success"))

    async def break_block(self, operation: BuildOperation) -> bool:
        response = await self.server.request("break_block", {"position": operation.position.to_dict(),
            "temporary": operation.temporary})
        self.last_action_reason = response.get("reason", "")
        return bool(response.get("success"))

    async def interaction_world(self, target: Vec3i) -> WorldState:
        world = await self.world_state()
        bounds = Bounds(target.offset(-4, -4, -4), target.offset(4, 3, 4))
        response = await self.server.request("observe_region", {"region": bounds.to_dict()})
        if not response.get("success") or any(not e.get("loaded") for e in response.get("blocks", [])):
            raise RuntimeError(response.get("reason", "interaction terrain unloaded"))
        self.server._apply_observation({"blocks": response["blocks"]})
        # Target-centered bounds permit planning beyond the current player's small sensor radius.
        return replace(world, observed_bounds=bounds)

    async def inspect_block(self, position: Vec3i) -> tuple[str, dict[str, str]]:
        response = await self.server.request("observe_block", {"position": position.to_dict()}, timeout=5.0)
        if not response.get("success") or not response.get("loaded", False):
            raise RuntimeError(response.get("reason", "target chunk not loaded"))
        block, props = response["observedBlock"], response.get("properties", {})
        self.server.observation.blocks[position] = block
        self.server.observation.properties[position] = props
        return block, props

    async def block_at(self, position: Vec3i) -> str:
        return (await self.inspect_block(position))[0]

    async def scan_region(self, bounds: Bounds) -> dict[Vec3i, tuple[str, dict[str, str]]]:
        result = {}
        # Small slices keep client-thread work bounded.
        for y in range(bounds.minimum.y, bounds.maximum.y + 1):
            response = await self.server.request("observe_region", {"region": Bounds(
                Vec3i(bounds.minimum.x, y, bounds.minimum.z), Vec3i(bounds.maximum.x, y, bounds.maximum.z)).to_dict()})
            if not response.get("success"):
                raise RuntimeError(response.get("reason", "region scan failed"))
            for entry in response["blocks"]:
                if not entry.get("loaded"):
                    raise RuntimeError("region contains unloaded chunks")
                result[Vec3i(**entry["position"])] = (entry["block"], entry.get("properties", {}))
        return result

    async def close(self) -> None:
        await self.server.close()


class RemoteNavigationProvider(NavigationProvider):
    def __init__(self, server: FabricSessionServer) -> None:
        self.server = server

    async def navigate(self, goal: NavigationGoal, world: WorldState) -> NavigationResult:
        eye = world.player.eye
        centered = eye is None or (eye[0]-goal.target.x-.5)**2 + (eye[2]-goal.target.z-.5)**2 < .04
        if world.player.position == goal.target and centered:
            return NavigationResult(True, goal.target, "already at interaction position")
        LOG.debug("navigation started", extra={"category": "NAVIGATION", "position": goal.target.to_dict()})
        response = await self.server.request("navigate", {"goal": goal.kind.value, "target": goal.target.to_dict(),
            "tolerance": goal.tolerance, "avoidHazards": goal.avoid_hazards}, timeout=125.0)
        LOG.debug("navigation finished", extra={"category": "NAVIGATION", "reason": response.get("reason", "")})
        return NavigationResult(bool(response.get("success")), Vec3i(**response.get("position", world.player.position.to_dict())),
                                response.get("reason", ""), bool(response.get("usedAlternative", False)))

    async def cancel(self) -> None:
        await self.server.request("cancel_navigation", {}, timeout=5.0, control=True)

import asyncio
import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "ai-core" / "src"))

from blockmind.network import FabricSessionServer
from blockmind.protocol import AdapterMetadata, CapabilityError, Envelope, NdjsonSession, ProtocolError


def metadata(version="1.20.1", capabilities=None):
    return {"minecraft": version, "adapterVersion": "0.1.1-dev", "protocol": "0.1.0",
            "capabilities": capabilities or ["OBSERVE_BLOCKS", "NAVIGATE"],
            "navigation": {"provider": "baritone", "available": True}}


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = FabricSessionServer(port=0)
        await self.server.start()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            client.writer.close()
        await self.server.close()

    async def connect(self, payload=None):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        session = NdjsonSession(reader, writer)
        self.clients.append(session)
        await session.send(Envelope("hello", payload or metadata()))
        ack = await session.receive()
        self.assertEqual(ack.type, "hello_ack")
        await self.server.wait_connected(.5)
        return session

    async def test_handshake_version_metadata_and_capability_gate(self):
        await self.connect(metadata("26.3", ["OBSERVE_BLOCKS"]))
        self.assertEqual(self.server.metadata.minecraft, "26.3")
        with self.assertRaises(CapabilityError):
            await self.server.request("place_block", {})

    async def test_tcp_connection_alone_is_not_ready(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        self.clients.append(NdjsonSession(reader, writer))
        with self.assertRaises(asyncio.TimeoutError):
            await self.server.wait_connected(.03)
        with self.assertRaises(ConnectionError):
            await self.server.request("observe", {})

    async def test_second_client_cannot_take_over_negotiated_session(self):
        first = await self.connect(metadata("1.21.11"))
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        self.clients.append(NdjsonSession(reader, writer))
        self.assertEqual(await asyncio.wait_for(reader.read(), .5), b"")
        self.assertIsNotNone(self.server.session)
        self.assertEqual(self.server.metadata.minecraft, "1.21.11")
        self.assertFalse(first.writer.is_closing())

    async def test_oversized_message_is_rejected_without_poisoning_next_session(self):
        session = await self.connect()
        session.writer.write(b"x" * 1_048_577 + b"\n")
        await session.writer.drain()
        error = await session.receive()
        self.assertEqual(error.type, "error")
        self.assertEqual(await session.reader.read(), b"")
        await asyncio.sleep(.01)
        await self.connect(metadata("26.3"))
        self.assertEqual(self.server.metadata.minecraft, "26.3")

    async def test_protocol_mismatch_and_malformed_message_rejected(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        writer.write(b'{"protocol":"9.0.0","id":"bad","type":"hello","payload":{}}\n')
        await writer.drain()
        value = json.loads(await reader.readline())
        self.assertIn("unsupported protocol", value["payload"]["reason"])
        self.assertEqual(await reader.readline(), b"")
        writer.close()
        await asyncio.sleep(.01)
        session = await self.connect()
        session.writer.write(b'not-json\n')
        await session.writer.drain()
        response = await session.receive()
        self.assertIn("malformed", response.payload["reason"])

    async def test_ids_responses_and_duplicate_responses(self):
        session = await self.connect()
        work = asyncio.create_task(self.server.request("observe_block", {"position": {"x": 0, "y": 64, "z": 0}}))
        request = await session.receive()
        reply = Envelope("action_result", {"success": True, "observedBlock": "minecraft:stone"}, request.id)
        await session.send(reply)
        await session.send(reply)
        self.assertTrue((await work)["success"])
        self.assertFalse(self.server._pending)

    async def test_emergency_control_bypasses_blocked_navigation(self):
        session = await self.connect()
        navigation = asyncio.create_task(self.server.request("navigate", {}))
        moving = await session.receive()
        stop = asyncio.create_task(self.server.request("emergency_stop", {}, control=True))
        control = await asyncio.wait_for(session.receive(), .5)
        self.assertEqual(control.type, "control")
        await session.send(Envelope("action_result", {"success": False, "reason": "emergency_stop"}, moving.id))
        await session.send(Envelope("action_result", {"success": True}, control.id))
        self.assertFalse((await navigation)["success"])
        await stop

    async def test_disconnect_fails_pending_and_reconnect_requires_new_handshake(self):
        session = await self.connect()
        work = asyncio.create_task(self.server.request("observe", {}))
        await session.receive()
        session.writer.close()
        await session.writer.wait_closed()
        with self.assertRaises(ConnectionError):
            await work
        await self.connect(metadata("1.21.11"))
        self.assertEqual(self.server.metadata.minecraft, "1.21.11")

    async def test_timeout_halts_adapter_and_cleans_future(self):
        session = await self.connect()
        work = asyncio.create_task(self.server.request("observe", {}, timeout=.03))
        await session.receive()
        halt = await session.receive()
        self.assertEqual(halt.payload["kind"], "emergency_stop")
        await session.send(Envelope("action_result", {"success": True}, halt.id))
        with self.assertRaises(asyncio.TimeoutError):
            await work
        self.assertFalse(self.server._pending)

    def test_loopback_security_and_stable_version_metadata(self):
        with self.assertRaises(ValueError):
            FabricSessionServer("0.0.0.0")
        for version in ("1.20.1", "1.20.6", "1.21.11", "26.3"):
            self.assertEqual(AdapterMetadata.parse(metadata(version)).minecraft, version)
        with self.assertRaises(ProtocolError):
            AdapterMetadata.parse({"minecraft": "1.20.1"})

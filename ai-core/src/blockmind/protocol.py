from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


PROTOCOL_VERSION = "0.1.0"
MAX_MESSAGE_BYTES = 1_048_576


class ProtocolError(ValueError):
    pass


class CapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterMetadata:
    minecraft: str
    adapter_version: str
    capabilities: frozenset[str]
    navigation: dict[str, Any]

    @classmethod
    def parse(cls, payload: dict[str, Any]) -> "AdapterMetadata":
        for key in ("minecraft", "adapterVersion", "protocol"):
            if not isinstance(payload.get(key), str) or not payload[key]:
                raise ProtocolError(f"hello missing {key}")
        if payload["protocol"] != PROTOCOL_VERSION:
            raise ProtocolError(f"unsupported protocol: {payload['protocol']}")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list) or not all(isinstance(c, str) for c in capabilities):
            raise ProtocolError("hello capabilities must be an array of strings")
        navigation = payload.get("navigation")
        if not isinstance(navigation, dict) or not isinstance(navigation.get("available"), bool):
            raise ProtocolError("hello navigation availability missing")
        return cls(payload["minecraft"], payload["adapterVersion"], frozenset(capabilities), navigation)

    def require(self, *capabilities: str) -> None:
        missing = set(capabilities) - self.capabilities
        if missing:
            raise CapabilityError(f"adapter lacks required capabilities: {', '.join(sorted(missing))}")


@dataclass
class Envelope:
    type: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    protocol: str = PROTOCOL_VERSION

    def encode(self) -> bytes:
        return (json.dumps({"protocol": self.protocol, "id": self.id or str(uuid4()),
                            "type": self.type, "payload": self.payload}, separators=(",", ":")) + "\n").encode()


class NdjsonSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self._send_lock = asyncio.Lock()

    async def send(self, message: Envelope) -> None:
        encoded = message.encode()
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message exceeds size limit")
        async with self._send_lock:
            self.writer.write(encoded)
            await self.writer.drain()

    async def receive(self) -> Envelope:
        line = await self.reader.readline()
        if not line:
            raise EOFError("Minecraft adapter disconnected")
        if len(line) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message exceeds size limit")
        try:
            data = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProtocolError("malformed JSON") from exc
        if not isinstance(data, dict):
            raise ProtocolError("envelope must be an object")
        if data.get("protocol") != PROTOCOL_VERSION:
            raise ProtocolError(f"unsupported protocol: {data.get('protocol')}")
        if not isinstance(data.get("type"), str) or not isinstance(data.get("payload"), dict):
            raise ProtocolError("invalid envelope type or payload")
        if not isinstance(data.get("id"), str) or not data["id"] or len(data["id"]) > 128:
            raise ProtocolError("invalid request id")
        return Envelope(data["type"], data.get("payload", {}), data.get("id", ""), data["protocol"])

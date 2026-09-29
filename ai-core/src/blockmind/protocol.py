from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


PROTOCOL_VERSION = "0.1.0"


@dataclass
class Envelope:
    type: str
    payload: dict[str, Any]
    id: str = ""
    protocol: str = PROTOCOL_VERSION

    def encode(self) -> bytes:
        return (json.dumps({"protocol": self.protocol, "id": self.id or str(uuid4()),
                            "type": self.type, "payload": self.payload}, separators=(",", ":")) + "\n").encode()


class NdjsonSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer

    async def send(self, message: Envelope) -> None:
        self.writer.write(message.encode())
        await self.writer.drain()

    async def receive(self) -> Envelope:
        line = await self.reader.readline()
        if not line:
            raise EOFError("Minecraft adapter disconnected")
        data = json.loads(line)
        if data.get("protocol") != PROTOCOL_VERSION:
            raise ValueError(f"unsupported protocol: {data.get('protocol')}")
        return Envelope(data["type"], data.get("payload", {}), data.get("id", ""), data["protocol"])

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .models import Vec3i
from .logging import configure_logging
from .navigation import SafeSimulatedNavigationProvider
from .network import FabricMinecraftPort, FabricSessionServer, RemoteNavigationProvider
from .runtime import BlockMindAgent, ProjectStore
from .simulation import SimulatedMinecraftPort


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="blockmind", description="BlockMind autonomous Minecraft agent")
    result.add_argument("prompt", help="Natural-language build request")
    result.add_argument("--origin", nargs=3, type=int, metavar=("X", "Y", "Z"), default=(0, 64, 0))
    result.add_argument("--simulate", action="store_true", help="Run against the deterministic in-memory adapter")
    result.add_argument("--listen", default="127.0.0.1:8765", help="Fabric adapter listen address")
    result.add_argument("--project-dir", type=Path, default=Path("projects"))
    return result


async def run(args: argparse.Namespace) -> int:
    origin = Vec3i(*args.origin)
    server = None
    if args.simulate:
        port = SimulatedMinecraftPort(origin.offset(dz=-3))
        navigation = SafeSimulatedNavigationProvider()
    else:
        host, port_text = args.listen.rsplit(":", 1)
        server = FabricSessionServer(host, int(port_text))
        await server.start()
        await server.wait_connected()
        port = FabricMinecraftPort(server)
        navigation = RemoteNavigationProvider(server)
    agent = BlockMindAgent(port, navigation)
    def progress(state, operation):
        completed = len(state.completed_operation_ids)
        if completed % 50 == 0 or completed == len(state.plan.operations):
            import logging
            logging.getLogger("blockmind.builder").info(
                "build progress", extra={"category": "BUILDER", "component_id": operation.component_id,
                                         "progress": round(state.progress * 100, 1)})
    project, report = await agent.run(args.prompt, origin, progress)
    path = ProjectStore(args.project_dir).save(project)
    print(json.dumps({
        "project_id": project.id,
        "status": project.status.value,
        "operations": len(project.plan.operations),
        "materials": project.plan.materials,
        "validation": report.__dict__ | {"verified": report.verified},
        "project_file": str(path),
    }, indent=2))
    if server:
        await server.close()
    return 0 if report.verified else 1


def main() -> None:
    configure_logging()
    raise SystemExit(asyncio.run(run(parser().parse_args())))


if __name__ == "__main__":
    main()

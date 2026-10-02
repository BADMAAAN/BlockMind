from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
from collections import Counter
from pathlib import Path

from .models import Bounds, Vec3i, BuildOperation, OperationKind
from .logging import configure_logging
from .navigation import SafeSimulatedNavigationProvider
from .network import FabricMinecraftPort, FabricSessionServer, RemoteNavigationProvider
from .runtime import BlockMindAgent, ProjectStore, Validator
from .simulation import SimulatedMinecraftPort
from .execution import ExecutionConfig

LOG = logging.getLogger("blockmind")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="blockmind", description="Experimental autonomous Minecraft agent")
    result.add_argument("prompt", nargs="?", help="Natural-language build request")
    result.add_argument("--origin", nargs=3, type=int, default=(0, 64, 0), metavar=("X", "Y", "Z"))
    result.add_argument("--simulate", action="store_true", help="Explicit in-memory simulation mode")
    result.add_argument("--listen", default="127.0.0.1:8765")
    result.add_argument("--project-dir", type=Path, default=Path("projects"))
    result.add_argument("--resume", type=Path, help="Load and reconcile an interrupted project")
    result.add_argument("--interactive", action="store_true", help="Read live controls from stdin during a build")
    result.add_argument("--config", type=Path)
    result.add_argument("--speed", choices=["safe", "normal", "fast", "max"])
    result.add_argument("--max-action-batch", type=int)
    result.add_argument("--placement-radius", type=float)
    result.add_argument("--creative-flight", action="store_true", help="Opt-in embodied Creative flight for elevated construction")
    result.add_argument("--reference", choices=["vscraft-enderman-legs", "vscraft-enderman"], help="Fixed reference reconstruction or partial probe; not arbitrary video support")
    result.add_argument("--mute-game-audio", action=argparse.BooleanOptionalAction, default=None)
    result.add_argument("--restore-audio-after-build", action=argparse.BooleanOptionalAction, default=None)
    result.add_argument("--benchmark-blocks", type=int, help="Developer-only partial foundation benchmark (not full acceptance)")
    result.add_argument("--benchmark-access", action="store_true", help="Developer-only 3x3 floor/wall access fixture from the house plan")
    result.add_argument("--benchmark-perimeter", action="store_true", help="Developer-only 8x8 support surface and four interleaved pane groups")
    result.add_argument("--legacy-scheduler", action="store_true", help="Developer-only frozen A/B ordering; requires a partial benchmark")
    result.add_argument("--acceptance-pause-after", type=int, help="Developer-only acknowledged pause/resume test after confirmed operations")
    result.add_argument("--acceptance-stop-after", type=int, help="Developer-only acknowledged STOP checkpoint; harness can reconnect and reconcile")
    result.add_argument("--command", choices=["status", "connection", "capabilities", "observe", "goto", "navigation-test",
        "place-test", "break-test", "cancel-navigation", "pause", "resume", "stop", "emergency-stop", "validate", "perf", "speed", "mute", "unmute"])
    result.add_argument("--target", nargs=3, type=int, metavar=("X", "Y", "Z"))
    result.add_argument("--block", default="minecraft:white_concrete")
    result.add_argument("--properties", nargs="*", default=[], metavar="KEY=VALUE")
    result.add_argument("--approve", nargs=6, type=int, metavar=("X1", "Y1", "Z1", "X2", "Y2", "Z2"),
                        help="Explicit permitted region for developer mutation tests")
    return result


async def developer_command(args, server, port, store):
    command = args.command
    if command == "perf":
        return await server.request("performance", {})
    if command in ("speed", "mute", "unmute"):
        config = ExecutionConfig.load(args.config or Path("blockmind.toml"))
        if command == "speed":
            config.speed_profile = args.speed or "fast"
        elif command == "mute":
            config.mute_game_audio = True
            # This one-shot connection closes immediately; keep mute for the
            # client session unless restoration was explicitly requested.
            config.restore_audio_after_build = False
        else:
            config.mute_game_audio = False
        if args.restore_audio_after_build is not None:
            config.restore_audio_after_build = args.restore_audio_after_build
        return await server.request("configure_execution", config.to_dict())
    if command in ("status", "connection", "capabilities"):
        meta = server.metadata
        return {"mode": "LIVE", "connected": server._connected.is_set(), "minecraft": meta.minecraft,
                "adapter": meta.adapter_version, "protocol": "0.1.0", "capabilities": sorted(meta.capabilities),
                "navigation": meta.navigation}
    if command == "observe":
        await port.world_state()
        return {"mode": "LIVE", "player": server.observation.player.__dict__}
    if command == "validate":
        if not args.resume:
            raise ValueError("validate requires --resume <project.json>")
        return (await Validator().validate(store.load(args.resume), port)).__dict__
    if command in ("pause", "resume", "stop", "emergency-stop", "cancel-navigation"):
        return await server.request(command.replace("-", "_"), {}, control=True)
    if args.target is None:
        raise ValueError(f"{command} requires --target X Y Z")
    target = Vec3i(*args.target)
    if command in ("goto", "navigation-test"):
        return await server.request("navigate", {"target": target.to_dict(), "avoidHazards": True}, timeout=125)
    if not args.approve:
        raise ValueError("place-test/break-test requires --approve X1 Y1 Z1 X2 Y2 Z2")
    region = Bounds(Vec3i(*args.approve[:3]), Vec3i(*args.approve[3:]))
    if not region.contains(target):
        raise ValueError("test target is outside approved region")
    world = await port.world_state()
    await server.request("approve_region", {"region": region.to_dict(), "temporaryRegion": region.to_dict(), "dimension": world.player.dimension})
    properties = dict(value.split("=", 1) for value in args.properties)
    return await server.request("place_block" if command == "place-test" else "break_block",
                                {"position": target.to_dict(), "block": args.block, "properties": properties})


async def interactive(agent, server):
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    def read_input():
        for line in sys.stdin:
            if loop.is_closed():
                return
            loop.call_soon_threadsafe(queue.put_nowait, line.strip())
    threading.Thread(target=read_input, daemon=True, name="blockmind-controls").start()
    LOG.info("controls: status | pause | resume | stop | emergency-stop")
    configuration = None
    async def configure():
        try:
            await agent.port.configure_execution(agent.config)
        except (ValueError, RuntimeError, ConnectionError) as exc:
            LOG.warning("configuration failed: %s", exc)
    while True:
        try:
            line = await queue.get()
        except asyncio.CancelledError:
            if configuration:
                configuration.cancel()
                await asyncio.gather(configuration, return_exceptions=True)
            raise
        try:
            if line == "perf":
                builder = getattr(agent, "builder", None)
                print(json.dumps(builder.metrics.snapshot() if builder else {}, default=str), flush=True)
            elif line.startswith("speed ") or line in ("mute", "unmute"):
                if configuration and not configuration.done():
                    LOG.warning("previous configuration is still pending; controls remain available")
                    continue
                value = agent.config.to_dict()
                if line.startswith("speed "): value["speed_profile"] = line.split()[1]
                else: value["mute_game_audio"] = line == "mute"
                updated = ExecutionConfig(**value)
                agent.config.__dict__.update(updated.__dict__)
                # Do not block reading STOP while configuration waits behind navigation.
                configuration = asyncio.create_task(configure())
                if getattr(agent, "project", None): agent.project.execution = agent.config.to_dict()
            elif line == "status":
                project = getattr(agent, "project", None)
                print(json.dumps({"mode": "SIMULATION" if server is None else "LIVE",
                    "progress": project.progress if project else 0, "paused": not agent.control._gate.is_set(),
                    "stopped": agent.control.stopped}), flush=True)
            else:
                if line in ("stop", "emergency-stop", "emergency_stop") and configuration:
                    configuration.cancel()
                    await asyncio.gather(configuration, return_exceptions=True)
                await agent.send_control(line.replace("-", "_"))
        except (ValueError, ConnectionError) as exc:
            LOG.warning("control failed: %s", exc)


async def run(args: argparse.Namespace) -> int:
    if args.legacy_scheduler and not (args.benchmark_blocks or args.benchmark_access or args.benchmark_perimeter):
        raise ValueError("legacy scheduling is restricted to developer partial benchmarks")
    if not args.prompt and not args.resume and not args.command and not args.reference:
        raise ValueError("provide a prompt, --resume project.json, or --command")
    mode = "SIMULATION" if args.simulate else "LIVE"
    LOG.info("MODE: %s", mode, extra={"mode": mode})
    origin = Vec3i(*args.origin)
    store = ProjectStore(args.project_dir)
    server = None
    controls = None
    agent = None
    pause_test = None
    stop_test = None
    try:
        if args.simulate:
            if args.command:
                raise ValueError("developer connection commands require LIVE mode")
            port = SimulatedMinecraftPort(origin.offset(dz=-3))
            navigation = SafeSimulatedNavigationProvider()
        else:
            host, number = args.listen.rsplit(":", 1)
            server = FabricSessionServer(host, int(number))
            await server.start()
            await server.wait_connected()
            port = FabricMinecraftPort(server)
            navigation = RemoteNavigationProvider(server)
            if args.command:
                response = await developer_command(args, server, port, store)
                print(json.dumps(response, indent=2, default=str))
                if args.command == "validate":
                    return 0 if response["expected"] == response["correct"] and not any(
                        response[key] for key in ("missing", "incorrect", "extra_permanent", "temporary_remaining")) else 1
                return 0 if response.get("success", True) else 1
            server.metadata.require("OBSERVE_BLOCKS", "PLACE_BLOCK", "BREAK_BLOCK", "CREATIVE_PROVISION",
                                    "NAVIGATE", "CANCEL_NAVIGATION", "BLOCK_STATE_ORIENTATION")
        loaded = store.load(args.resume) if args.resume else None
        config = ExecutionConfig(**loaded.execution) if loaded and loaded.execution and not args.config else ExecutionConfig.load(args.config or Path("blockmind.toml"))
        values = config.to_dict()
        for field, arg in (("speed_profile", "speed"), ("max_action_batch", "max_action_batch"), ("placement_radius", "placement_radius"),
                           ("mute_game_audio", "mute_game_audio"), ("restore_audio_after_build", "restore_audio_after_build")):
            if getattr(args, arg) is not None: values[field] = getattr(args, arg)
        config = ExecutionConfig(**values)
        if args.creative_flight: config.creative_flight = True
        agent = BlockMindAgent(port, navigation, config=config)
        agent.legacy_scheduler = args.legacy_scheduler
        if args.acceptance_pause_after:
            async def verify_pause():
                while not hasattr(agent, "builder") or len(agent.project.completed_operation_ids) < args.acceptance_pause_after:
                    await asyncio.sleep(.05)
                await agent.send_control("pause")
                before = agent.builder.metrics.counts["operation_attempts"]
                store.save(agent.project)
                await asyncio.sleep(1)  # Intentional acceptance pause, never a placement pacing delay.
                after = agent.builder.metrics.counts["operation_attempts"]
                await agent.send_control("resume")
                agent.project.scheduler["pause_test"] = {"pause_acknowledged": True, "resume_acknowledged": True,
                    "attempts_before": before, "attempts_after": after, "no_new_attempts_while_paused": before == after}
                LOG.info("ACCEPTANCE pause/resume acknowledged attempts=%s/%s", before, after)
            pause_test = asyncio.create_task(verify_pause())
        if args.acceptance_stop_after:
            async def verify_stop():
                while not hasattr(agent, "builder") or len(agent.project.completed_operation_ids) < args.acceptance_stop_after:
                    await asyncio.sleep(.05)
                await agent.send_control("stop")
                agent.project.scheduler["stop_test"] = {"stop_acknowledged": True,
                    "checkpoint_completed_ids": len(agent.project.completed_operation_ids),
                    "owned_temporary_intents": len(agent.project.temporary_blocks)}
                store.save(agent.project)
                LOG.info("ACCEPTANCE acknowledged STOP checkpoint before reconnect")
            stop_test = asyncio.create_task(verify_stop())
        if args.interactive:
            controls = asyncio.create_task(interactive(agent, server))
        def progress(state, operation):
            completed = len(state.completed_operation_ids)
            if completed and (completed % 50 == 0 or completed == len(state.plan.operations)):
                LOG.info("build progress", extra={"category": "BUILDER", "component_id": operation.component_id,
                         "progress": round(state.progress * 100, 1)})
        if args.resume:
            project, report = await agent.run_project(loaded, progress, store, reconcile=True)
        elif args.reference:
            from .reference_builds import ENDERMAN_LEGS, enderman_project
            grass = "minecraft:grass" if server and server.metadata.minecraft == "1.20.1" else "minecraft:short_grass"
            project = enderman_project(origin,grass) if args.reference == "vscraft-enderman" else ENDERMAN_LEGS.legs_probe(origin)
            project, report = await agent.run_project(project,progress,store)
        elif args.benchmark_blocks or args.benchmark_access or args.benchmark_perimeter:
            if args.benchmark_blocks and not 1 <= args.benchmark_blocks <= 256:
                raise ValueError("benchmark blocks must be 1..256")
            project = agent.plan(args.prompt, origin)
            if args.benchmark_perimeter:
                project.design.parameters.update(width=8, depth=8, floors=1)
                project.plan.operations = [BuildOperation(OperationKind.PLACE, origin.offset(x,y,z), "minecraft:dark_oak_planks",
                    "foundation" if y==0 else "floor_1.slab") for y in (0,1) for z in range(8) for x in range(8)]
                project.plan.operations += [BuildOperation(OperationKind.PLACE, origin.offset(x,y,z), "minecraft:glass_pane", "floor_1.wall_"+side)
                    for y in (2,3) for i in range(2,6) for side,x,z in (("north",i,0),("south",i,7),("east",7,i),("west",0,i))]
            elif args.benchmark_access:
                project.plan.operations = [op for op in project.plan.operations if
                    origin.x <= op.position.x < origin.x+3 and origin.z <= op.position.z < origin.z+3
                    and origin.y <= op.position.y <= origin.y+3]
            else:
                project.plan.operations = [op for op in project.plan.operations if op.component_id == "foundation"][:args.benchmark_blocks]
            project.plan.materials = dict(Counter(op.block for op in project.plan.operations if op.block and not op.verify_only))
            project, report = await agent.run_project(project, progress, store)
        else:
            project, report = await agent.run(args.prompt, origin, progress, store)
        path = store.save(project)
        print(json.dumps({"mode": mode, "project_id": project.id, "status": project.status.value,
            "operations": len(project.plan.operations), "materials": project.plan.materials,
            "validation": report.__dict__ | {"verified": report.verified}, "project_file": str(path)}, indent=2))
        LOG.info("PERF final", extra={"category": "PERF", "blocks": project.performance})
        return 0 if report.verified and project.status.value == "complete" else 1
    finally:
        for acceptance_test in (pause_test, stop_test):
            if acceptance_test is None: continue
            if acceptance_test.done() and not acceptance_test.cancelled(): acceptance_test.result()
            else:
                acceptance_test.cancel()
                await asyncio.gather(acceptance_test, return_exceptions=True)
        if controls:
            controls.cancel()
            await asyncio.gather(controls, return_exceptions=True)
        if server:
            await server.close()


def main() -> None:
    configure_logging()
    try:
        raise SystemExit(asyncio.run(run(parser().parse_args())))
    except (ValueError, RuntimeError, ConnectionError, asyncio.TimeoutError) as exc:
        LOG.error("execution failed: %s", exc)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        LOG.warning("interrupted; adapter halted and project checkpoint retained")
        raise SystemExit(130)


if __name__ == "__main__":
    main()

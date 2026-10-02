"""Launch an isolated client test world and the real Core; never substitute simulation."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-core/src"))
from blockmind.cli import parser, run
from blockmind.logging import configure_logging, JsonFormatter


async def revalidate_owned_world(project_path, directory):
    """Read-only validation after native restart; NEVER execute/repair a plan."""
    from blockmind.network import FabricSessionServer, FabricMinecraftPort
    from blockmind.runtime import ProjectStore, Validator
    from blockmind.models import ProjectStatus
    from blockmind.performance import counter_delta
    store=ProjectStore(directory/'projects')
    project=store.load(project_path)
    server=FabricSessionServer()
    started=time.monotonic()
    try:
        await server.start(); await server.wait_connected()
        port=FabricMinecraftPort(server)
        world=await port.world_state()
        if project.dimension != world.player.dimension:
            raise RuntimeError('saved test dimension does not match; no mutations allowed')
        before=await server.request('performance',{})
        report=await Validator().validate(project,port)
        after=await server.request('performance',{})
        if counter_delta(before,after,'issuedPlacements') != 0:
            raise RuntimeError('read-only placement counter is unverified or changed')
        project.status=ProjectStatus.COMPLETE if report.verified else ProjectStatus.FAILED
        project.performance={'mode':'READ_ONLY_REVALIDATION_NOT_BUILD_TIMING',
            'total_run_seconds':time.monotonic()-started,'mutation_attempts':0,
            'before_configuration':before,'adapter':after,'transport':server.metrics.snapshot()}
        store.save(project)
        return 0 if report.verified else 1
    finally:
        await server.close()

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--java-home", type=Path, required=True)
    arguments.add_argument("--timeout", type=int, default=3600)
    arguments.add_argument("--speed", choices=["safe", "normal", "fast", "max"], default="fast")
    arguments.add_argument("--creative-flight", action="store_true", help="Opt-in Creative key-steered flight in the disposable world")
    arguments.add_argument("--reference", choices=["vscraft-enderman-legs", "vscraft-enderman"], help="Fixed authorized Enderman reconstruction or partial legs probe")
    arguments.add_argument("--benchmark-blocks", type=int)
    arguments.add_argument("--benchmark-access", action="store_true")
    arguments.add_argument("--benchmark-perimeter", action="store_true")
    arguments.add_argument("--legacy-scheduler", action="store_true")
    arguments.add_argument("--restart-after", type=int, help="Opt-in STOP/Core-session reconnect in the SAME disposable world")
    arguments.add_argument("--resume-project", type=Path, help="Revalidate the last owned completed test world after client failure; never create/teleport")
    args = arguments.parse_args()
    if args.restart_after is not None and args.restart_after < 1:
        arguments.error("--restart-after must be positive")
    resume_world=None
    if args.resume_project:
        args.resume_project=args.resume_project.resolve()
        own_runs=(ROOT/'build/live-test').resolve()
        if not args.resume_project.is_relative_to(own_runs) or args.restart_after or args.reference != 'vscraft-enderman':
            arguments.error('--resume-project requires an owned full-reference checkpoint and no --restart-after')
        source_result=json.loads((args.resume_project.parent.parent/'result.json').read_text(encoding='utf-8'))
        if not source_result.get('world_validation_verified') or Path(source_result['project_file']).resolve()!=args.resume_project:
            arguments.error('source run must have verified the whole world before its client failure')
        # Fixed dev run directory only. Caller must preserve the completed last
        # world; no automatic search/open of personal worlds is permitted.
        resume_world=(ROOT/'minecraft-mod/build/run/clientGameTest/saves/New World').resolve()
        if not (resume_world/'level.dat').is_file():
            arguments.error('last owned disposable world is absent; do not substitute another world')
    directory = ROOT / "build/live-test" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    directory.mkdir(parents=True)
    version = "1.17.0"
    with urllib.request.urlopen(f"https://api.github.com/repos/cabaletta/baritone/releases/tags/v{version}") as response:
        metadata = json.load(response)
    asset = next(a for a in metadata["assets"] if a["name"] == f"baritone-api-fabric-{version}.jar")
    binary = directory / asset["name"]
    with urllib.request.urlopen(asset["browser_download_url"]) as response:
        content = response.read()
    if "sha256:" + hashlib.sha256(content).hexdigest() != asset["digest"]:
        raise RuntimeError("official Baritone checksum mismatch")
    binary.write_bytes(content)
    # Loom's local file dependency does not put nested runtime jars on the dev classpath.
    # Extract only official dependency entries into this disposable test directory.
    nested = directory / "baritone-dependencies"
    nested.mkdir()
    with zipfile.ZipFile(binary) as archive:
        dependencies = json.loads(archive.read("fabric.mod.json")).get("jars", [])
        for dependency in dependencies:
            name = dependency["file"]
            (nested / Path(name).name).write_bytes(archive.read(name))
    env = os.environ.copy()
    env["JAVA_HOME"] = str(args.java_home)
    env["PATH"] = str(args.java_home / "bin") + os.pathsep + env["PATH"]
    env["ALSOFT_LOGLEVEL"] = "3"
    env["ALSOFT_LOGFILE"] = str(directory / "openal.log")
    wrapper = ROOT / "minecraft-mod" / ("gradlew.bat" if os.name == "nt" else "gradlew")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    configure_logging()
    core_log = logging.FileHandler(directory / "core.ndjson", encoding="utf-8")
    core_log.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(core_log)
    with (directory / "client.log").open("w", encoding="utf-8") as log:
        client = subprocess.Popen([str(wrapper), "runClientGameTest", "-Ptarget=1.21.11", "-PliveTest",
            f"-PbaritoneJar={binary}", f"-PbaritoneDependencies={nested}", f"-PtestDirectory={directory}"] +
            ([f"-PresumeWorld={resume_world}"] if resume_world else []) + ["--no-daemon", "--console=plain"],
            cwd=wrapper.parent, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        started = time.monotonic()
        result = {"mode": "LIVE", "verified": False}
        print(f"Live test logs: {directory}", flush=True)
        try:
            while not (directory / "ready").exists():
                if client.poll() is not None:
                    raise RuntimeError(f"client test exited before creating world (exit={client.returncode})")
                if time.monotonic() - started > args.timeout:
                    raise TimeoutError("client test startup timeout")
                time.sleep(1)
            cli_args = parser().parse_args([PROMPT, "--origin", "100", "-60", "100",
                "--project-dir", str(directory / "projects"), "--speed", args.speed] +
                (["--creative-flight"] if args.creative_flight else []) +
                (["--reference",args.reference] if args.reference else []) +
                (["--benchmark-blocks", str(args.benchmark_blocks)] if args.benchmark_blocks else []) +
                (["--benchmark-access"] if args.benchmark_access else []) +
                (["--benchmark-perimeter"] if args.benchmark_perimeter else []) +
                (["--legacy-scheduler"] if args.legacy_scheduler else []) +
                (["--acceptance-stop-after", str(args.restart_after)] if args.restart_after else []) +
                (["--acceptance-pause-after","40"] if args.reference else [] if args.benchmark_blocks or args.benchmark_access or args.benchmark_perimeter else ["--acceptance-pause-after", "221"]))
            if args.resume_project:
                cli_args=parser().parse_args(['--resume',str(args.resume_project),'--project-dir',str(directory/'projects'),
                    '--speed',args.speed]+(['--creative-flight'] if args.creative_flight else []))
                result['owned_world_resume']={'source_run':args.resume_project.parent.parent.name,
                    'same_saved_disposable_world':True,'new_client_process':True,'no_setup_teleport':True}
            async def bounded_run():
                if args.resume_project:
                    return await asyncio.wait_for(revalidate_owned_world(args.resume_project,directory),
                        max(1,args.timeout-(time.monotonic()-started)))
                async def remaining(options):
                    return await asyncio.wait_for(run(options), max(1, args.timeout - (time.monotonic() - started)))
                code = await remaining(cli_args)
                if args.restart_after:
                    checkpoint_file = next((directory / "projects").glob("*.json"))
                    checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                    if not checkpoint.get("scheduler", {}).get("stop_test", {}).get("stop_acknowledged"):
                        if code != 0:
                            result["session_restart"] = {"exercised":False,"reason":"build failed before requested STOP threshold"}
                            return code
                        raise RuntimeError("requested STOP/reconnect acceptance was not exercised")
                    result["session_restart"] = {"kind": "acknowledged STOP + Core-session reconnect, not native crash",
                        "same_disposable_world": True, "checkpoint_completed_ids": len(checkpoint["completed_operation_ids"]),
                        "owned_temporary_intents": len(checkpoint["temporary_blocks"]),
                        "before_reconnect_performance": checkpoint["performance"]}
                    # run() closed its listener/session. The SAME client/world
                    # remains alive, reconnects, re-approves and scans the region.
                    resumed_args = parser().parse_args(["--resume", str(checkpoint_file),
                        "--project-dir", str(directory / "projects"), "--speed", args.speed] +
                        (["--creative-flight"] if args.creative_flight else []))
                    code = await remaining(resumed_args)
                return code
            exit_code = asyncio.run(bounded_run())
            project_file = next((directory / "projects").glob("*.json"))
            project = json.loads(project_file.read_text(encoding="utf-8"))
            result = result | project["validation"] | {"mode": "LIVE", "verified": exit_code == 0,
                "retried_operations": sum(op["attempts"] > 1 for op in project["plan"]["operations"]),
                "project_file": str(project_file)}
            result["performance"] = project["performance"]
            if result.get("session_restart", {}).get("before_reconnect_performance"):
                result["aggregate_core_run_seconds"] = project["performance"]["total_run_seconds"] + result["session_restart"]["before_reconnect_performance"]["total_run_seconds"]
            result["scheduler"] = project.get("scheduler", {})
            result["benchmark"] = "full authorized Enderman reconstruction" if args.reference == "vscraft-enderman" else "partial Enderman legs geometry probe" if args.reference else "partial perimeter" if args.benchmark_perimeter else "partial vertical access" if args.benchmark_access else "partial foundation" if args.benchmark_blocks else "full acceptance house"
            result["ordering"] = "legacy_19db2c8" if args.legacy_scheduler else "global_scheduler"
            result["creative_flight"] = args.creative_flight
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc) or type(exc).__name__
            checkpoints = list((directory / "projects").glob("*.json"))
            if checkpoints:
                checkpoint = json.loads(checkpoints[0].read_text(encoding="utf-8"))
                result.update({"expected": len(checkpoint["plan"]["operations"]),
                    "last_checkpoint_completed": len(checkpoint["completed_operation_ids"]),
                    "final_world_counts": "NOT VERIFIED", "project_file": str(checkpoints[0])})
        finally:
            (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            if client.poll() is None:
                # Full-reference camera views are normal navigation AFTER Core
                # validation. Allow them to finish without inflating build time.
                deadline=time.monotonic()+(180 if args.reference == "vscraft-enderman" else 30)
                while client.poll() is None and time.monotonic()<deadline:
                    try:
                        client.wait(timeout=min(1,max(.01,deadline-time.monotonic())))
                    except subprocess.TimeoutExpired:
                        continue
                if client.poll() is None:
                    # Stop only the process tree launched by this test.
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(client.pid), "/T", "/F"], capture_output=True)
                    else:
                        client.terminate()
            result["client_exit_code"] = client.poll()
            client_output = (directory / "client.log").read_text(encoding="utf-8", errors="replace")
            native_exits = re.findall(r"finished with non-zero exit value (-?\d+)(?: \(NTSTATUS (0x[0-9A-Fa-f]+)\))?", client_output)
            if native_exits:
                result["minecraft_exit_code"] = int(native_exits[-1][0])
                result["minecraft_ntstatus"] = native_exits[-1][1] or None
            runtime = directory / "runtime-state.json"
            if runtime.exists(): result["last_runtime_state"] = json.loads(runtime.read_text(encoding="utf-8"))
            own_pid = result.get("last_runtime_state", {}).get("pid")
            if os.name == "nt" and isinstance(own_pid,int) and os.environ.get("LOCALAPPDATA"):
                # Copy only the exact disposable client's dump, never other Java/user dumps.
                own_dump = Path(os.environ["LOCALAPPDATA"]) / "CrashDumps" / f"java.exe.{own_pid}.dmp"
                if own_dump.exists(): shutil.copy2(own_dump,directory / own_dump.name)
            run_directory = ROOT / "minecraft-mod/build/run/clientGameTest"
            diagnostic_files = [run_directory / "logs/latest.log"]
            diagnostic_files += list((run_directory / "crash-reports").glob("*.txt"))
            diagnostic_files += list(directory.glob("hs_err_pid*.log"))
            for source in diagnostic_files:
                if source.exists() and source.parent != directory: shutil.copy2(source, directory / source.name)
            result["diagnostic_files"] = [str(path) for path in directory.iterdir() if path.is_file() and path.suffix in (".log", ".txt", ".dmp")]
            if result.get("verified") and result["client_exit_code"] != 0:
                result["world_validation_verified"] = True
                result["verified"] = False
                result["error"] = "world validation passed but client-test process did not exit successfully"
            if result.get('verified') and args.reference == 'vscraft-enderman':
                views_file=directory/'reference-views.json'
                views=json.loads(views_file.read_text(encoding='utf-8')).get('views',[]) if views_file.exists() else []
                result['camera_views']=views
                if len(views)!=3 or not all(view.get('arrived') for view in views):
                    result['world_validation_verified']=True
                    result['verified']=False
                    result['error']='world validation passed but whole-reference camera views are incomplete'
            (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2))
    return 0 if result.get("verified") and client.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Launch an isolated client test world and the real Core; never substitute simulation."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import logging
import os
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

PROMPT = "Build a small modern two-story house using white concrete and dark oak, with large windows and a small pool."


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--java-home", type=Path, required=True)
    arguments.add_argument("--timeout", type=int, default=3600)
    arguments.add_argument("--speed", choices=["safe", "normal", "fast", "max"], default="fast")
    arguments.add_argument("--benchmark-blocks", type=int)
    arguments.add_argument("--benchmark-access", action="store_true")
    args = arguments.parse_args()
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
    wrapper = ROOT / "minecraft-mod" / ("gradlew.bat" if os.name == "nt" else "gradlew")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    configure_logging()
    core_log = logging.FileHandler(directory / "core.ndjson", encoding="utf-8")
    core_log.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(core_log)
    with (directory / "client.log").open("w", encoding="utf-8") as log:
        client = subprocess.Popen([str(wrapper), "runClientGameTest", "-Ptarget=1.21.11", "-PliveTest",
            f"-PbaritoneJar={binary}", f"-PbaritoneDependencies={nested}", f"-PtestDirectory={directory}", "--no-daemon", "--console=plain"],
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
                (["--benchmark-blocks", str(args.benchmark_blocks)] if args.benchmark_blocks else []) +
                (["--benchmark-access"] if args.benchmark_access else []))
            async def bounded_run():
                return await asyncio.wait_for(run(cli_args), max(1, args.timeout - (time.monotonic() - started)))
            exit_code = asyncio.run(bounded_run())
            project_file = next((directory / "projects").glob("*.json"))
            project = json.loads(project_file.read_text(encoding="utf-8"))
            result = project["validation"] | {"mode": "LIVE", "verified": exit_code == 0,
                "retried_operations": sum(op["attempts"] > 1 for op in project["plan"]["operations"]),
                "project_file": str(project_file)}
            result["performance"] = project["performance"]
            result["benchmark"] = "partial vertical access" if args.benchmark_access else "partial foundation" if args.benchmark_blocks else "full acceptance house"
        except Exception as exc:
            result["error"] = str(exc)
            checkpoints = list((directory / "projects").glob("*.json"))
            if checkpoints:
                checkpoint = json.loads(checkpoints[0].read_text(encoding="utf-8"))
                result.update({"expected": len(checkpoint["plan"]["operations"]),
                    "last_checkpoint_completed": len(checkpoint["completed_operation_ids"]),
                    "final_world_counts": "NOT VERIFIED", "project_file": str(checkpoints[0])})
        finally:
            (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            if client.poll() is None:
                try:
                    client.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Stop only the process tree launched by this test.
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(client.pid), "/T", "/F"], capture_output=True)
                    else:
                        client.terminate()
            print(json.dumps(result, indent=2))
    return 0 if result.get("verified") and client.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

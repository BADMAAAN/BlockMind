"""Build pinned adapters; requires a JDK 25 Gradle runtime, emits auditable results."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append", help="Build just these pinned targets (repeatable)")
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--clean", action="store_true", help="Clean each target before building and testing")
    args = parser.parse_args()
    targets = json.loads((ROOT / "minecraft-mod/targets.json").read_text())
    selected = args.target or list(targets)
    if any(target not in targets for target in selected):
        parser.error("unknown target")
    env = os.environ.copy()
    if args.java_home:
        env["JAVA_HOME"] = str(args.java_home)
        env["PATH"] = str(args.java_home / "bin") + os.pathsep + env["PATH"]
    wrapper = ROOT / "minecraft-mod" / ("gradlew.bat" if os.name == "nt" else "gradlew")
    results = []
    for target in selected:
        print(f"Building Minecraft {target}", flush=True)
        tasks = ["clean", "build"] if args.clean else ["build"]
        code = subprocess.call([str(wrapper), *tasks, f"-Ptarget={target}", "--no-daemon",
                                "--no-configuration-cache", "--console=plain"], cwd=wrapper.parent, env=env)
        results.append({"minecraft": target, "build": "PASS" if code == 0 else "FAIL", "runtime": "NOT VERIFIED"})
    output = ROOT / "build" / "adapter-build-results.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return int(any(result["build"] != "PASS" for result in results))


if __name__ == "__main__":
    sys.exit(main())

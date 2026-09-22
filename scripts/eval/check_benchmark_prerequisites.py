#!/usr/bin/env python3
"""Check the local prerequisites before running Yuxi benchmark jobs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen


def check_file(path: Path, label: str, required: bool = True) -> tuple[bool, str]:
    exists = path.exists()
    status = "OK" if exists else ("MISSING" if required else "PENDING")
    return exists or not required, f"{status}: {label} ({path})"


def check_command(command: str) -> tuple[bool, str]:
    available = shutil.which(command) is not None
    return available, f"{'OK' if available else 'MISSING'}: command {command}"


def check_api_health() -> tuple[bool, str]:
    try:
        with urlopen("http://localhost:5050/api/system/health", timeout=5) as response:
            payload = json.load(response)
        healthy = payload.get("status") == "ok"
        return healthy, f"{'OK' if healthy else 'FAIL'}: Yuxi API health ({payload.get('status')})"
    except Exception as exc:
        return False, f"MISSING: Yuxi API health ({exc})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--strict", action="store_true", help="Fail when raw datasets or artifact outputs are missing")
    args = parser.parse_args()

    checks = [
        check_file(args.root / "benchmarks/registry.json", "benchmark registry"),
        check_file(args.root / "benchmarks/source-lock.json", "source lock"),
        check_file(args.root / "benchmarks/selection.json", "selection policy"),
        check_command("docker"),
        check_command("curl"),
        check_api_health(),
    ]
    for passed, message in checks:
        print(message)

    pending = [
        "benchmarks/raw",
        "benchmarks/artifacts",
        "benchmarks/results",
    ]
    workspace_ready = True
    for relative in pending:
        path = args.root / relative
        workspace_ready = workspace_ready and path.exists()
        print(f"{'OK' if path.exists() else 'PENDING'}: workspace {path}")

    return 0 if all(passed for passed, _ in checks) and (workspace_ready or not args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())

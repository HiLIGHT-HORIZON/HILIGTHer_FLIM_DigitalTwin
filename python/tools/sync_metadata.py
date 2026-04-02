#!/usr/bin/env python3
"""Sync derived project version fields from python/metadata.py.

`python/metadata.py` is the single source of truth.
This helper updates secondary package manifests that cannot import Python code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from metadata import get_build_label, get_release_label, get_version


def sync_frontend_package(root: Path) -> None:
    version = get_version()
    package_json = root / "python" / "frontend" / "package.json"
    package_lock = root / "python" / "frontend" / "package-lock.json"

    if package_json.exists():
        payload = json.loads(package_json.read_text(encoding="utf-8"))
        payload["version"] = version
        package_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if package_lock.exists():
        payload = json.loads(package_lock.read_text(encoding="utf-8"))
        payload["version"] = version
        if isinstance(payload.get("packages"), dict) and "" in payload["packages"]:
            payload["packages"][""]["version"] = version
        package_lock.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    sync_frontend_package(ROOT)
    print(f"Synced HILIGHTer metadata: v{get_release_label()} | {get_build_label()}")


if __name__ == "__main__":
    main()

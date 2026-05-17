from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.memory import COLLECTIONS


def empty_store() -> dict[str, Any]:
    return {name: {} if name == "user_profiles" else [] for name in COLLECTIONS}


def load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_store()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    for name, empty_value in empty_store().items():
        data.setdefault(name, empty_value.copy() if isinstance(empty_value, dict) else [])
    return data


def write_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def count_records(data: dict[str, Any]) -> dict[str, int]:
    counts = {}
    for name in COLLECTIONS:
        value = data.get(name, {} if name == "user_profiles" else [])
        counts[name] = len(value) if isinstance(value, (dict, list)) else 0
    return counts


def clear_user(data: dict[str, Any], user_id: str) -> dict[str, Any]:
    cleared = empty_store()
    cleared["user_profiles"] = {
        key: value
        for key, value in data.get("user_profiles", {}).items()
        if key != user_id and value.get("user_id") != user_id
    }
    for name in COLLECTIONS:
        if name == "user_profiles":
            continue
        cleared[name] = [
            item for item in data.get(name, []) if not isinstance(item, dict) or item.get("user_id") != user_id
        ]
    return cleared


def backup_store(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for name in COLLECTIONS:
        print(f"  {name}: {counts[name]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear AITrading JSON memory for fresh-user or clean-state testing.",
    )
    parser.add_argument(
        "--memory-path",
        type=Path,
        default=ROOT / "data" / "memory_store.json",
        help="Memory JSON path. Defaults to AITrading/data/memory_store.json.",
    )
    parser.add_argument(
        "--user-id",
        default="",
        help="Only clear records for this user_id. Omit to clear all memory collections.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run preview.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a timestamped .bak copy before applying changes.",
    )
    args = parser.parse_args()

    memory_path = args.memory_path.resolve()
    before = load_store(memory_path)
    after = clear_user(before, args.user_id) if args.user_id else empty_store()

    mode = f"user_id={args.user_id}" if args.user_id else "all users"
    print(f"Memory path: {memory_path}")
    print(f"Clear mode: {mode}")
    print_counts("Before:", count_records(before))
    print_counts("After:", count_records(after))

    if not args.yes:
        print("Dry run only. Re-run with --yes to apply.")
        return 0

    backup_path = None
    if memory_path.exists() and not args.no_backup:
        backup_path = backup_store(memory_path)

    write_store(memory_path, after)
    print("Memory cleared.")
    if backup_path:
        print(f"Backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.server import run


def load_env(path: Path = ROOT / "config" / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the AITrading backend for frontend integration.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    load_env()
    base_url = f"http://{args.host}:{args.port}"
    print("AITrading backend dev server")
    print(f"  URL: {base_url}")
    print(f"  OpenAPI: {ROOT / 'openapi.yaml'}")
    print("  Key endpoints:")
    print("    GET  /health")
    print("    GET  /api/questionnaires")
    print("    GET  /api/questionnaires/full_assessment")
    print("    POST /api/questionnaires/full_assessment/submit")
    print("    POST /api/training/check")
    print("    POST /api/review/run")
    print("    GET  /api/memory")
    run(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

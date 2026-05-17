from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.memory import MemoryStore
from backend.app.orchestrator import Orchestrator


def run_case(name: str, orchestrator: Orchestrator, payload: dict) -> None:
    result = orchestrator.run(payload)
    print(f"\n== {name} ==")
    print(json.dumps(
        {
            "entry": result["entry"],
            "intent": result["intent"],
            "report": result["report"],
            "trace": [item["name"] for item in result["tool_trace"]],
            "memory_written": result["memory_written"],
        },
        ensure_ascii=False,
        indent=2,
    ))


def main() -> None:
    os.environ["EASTMONEY_REPORT_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_PUSH2_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_PUSH2HIS_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_ANNOUNCEMENT_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_HSF10_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["DUCKDUCKGO_SEARCH_BASE_URL"] = "http://127.0.0.1:9"
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(Path(tmpdir) / "memory.json")
        orchestrator = Orchestrator(store)
        run_case(
            "assessment",
            orchestrator,
            {
                "user_id": "u_001",
                "entry": "assessment",
                "answers": [
                    "我会先确定最大亏损和止损，再看盈亏比。",
                    "连续亏损后会暂停交易并复盘策略是否失效。",
                    "我记录每一笔交易并总结执行问题。",
                ],
            },
        )
        run_case(
            "training",
            orchestrator,
            {
                "user_id": "u_001",
                "entry": "training",
                "message": "我今天买入某股票，仓位30%，现在想加仓",
                "form_data": {
                    "stock": "某股票",
                    "position": 30,
                    "reason": "最近三天涨得很强",
                    "holding_period": "短线",
                    "emotion": "担心踏空",
                },
            },
        )
        run_case(
            "review",
            orchestrator,
            {
                "user_id": "u_001",
                "entry": "review",
                "self_reflection": "这次有点追涨，亏损后想补仓，原计划没有执行。",
                "trade_record": {
                    "stock": "某股票",
                    "buy_price": 18.6,
                    "sell_price": 17.2,
                    "position": 50,
                    "buy_reason": "短期上涨",
                    "followed_plan": "否",
                    "emotion": "害怕踏空",
                },
            },
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .memory import MemoryStore
from .orchestrator import Orchestrator
from .questionnaire_engine import QuestionnaireAnswerValidationError, run_questionnaire_assessment
from .questionnaire_store import get_questionnaire, list_questionnaires
from .research import broker_report_search
from .training_agent import run_training_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-trading-backend")
    parser.add_argument("--memory-path", default=None, help="Optional JSON memory store path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    orchestrate = subparsers.add_parser("orchestrate", help="Run the unified orchestrator.")
    orchestrate.add_argument("--payload", required=True, help="JSON payload string or @path/to/payload.json.")

    training = subparsers.add_parser("training", help="Run behavior training check.")
    training.add_argument("--user-id", default="cli_user")
    training.add_argument("--scenario", default="", help="One of buy, hold, add, reduce, loss, chase, check. Omit to infer from message.")
    training.add_argument("--message", default="")
    training.add_argument("--use-llm", action="store_true", help="Ask Kimi/OpenAI-compatible endpoint for final training wording.")
    training.add_argument("--form-json", default="{}", help="Trade plan JSON object.")

    assessment = subparsers.add_parser("assessment", help="Run ability assessment.")
    assessment.add_argument("--user-id", default="cli_user")
    assessment.add_argument("--answers-json", default="[]", help="Assessment answers JSON array.")

    review = subparsers.add_parser("review", help="Run trade review.")
    review.add_argument("--user-id", default="cli_user")
    review.add_argument("--message", default="")
    review.add_argument("--trade-json", default="{}", help="Trade record JSON object.")
    review.add_argument("--trade-table-json", default="", help="Optional table rows JSON array; converted to trade record.")
    review.add_argument("--self-reflection", default="")
    review.add_argument("--use-llm", action="store_true", help="Ask Kimi/OpenAI-compatible endpoint for final review wording.")

    research = subparsers.add_parser("research", help="Search public research background.")
    research.add_argument("--query", required=True)
    research.add_argument("--limit", type=int, default=5)

    questionnaires = subparsers.add_parser("questionnaires", help="List questionnaire configs.")

    questionnaire = subparsers.add_parser("questionnaire", help="Show or submit one questionnaire.")
    questionnaire.add_argument("action", choices=["show", "submit"])
    questionnaire.add_argument("--id", required=True, help="Questionnaire id.")
    questionnaire.add_argument("--user-id", default="cli_user")
    questionnaire.add_argument("--answers-json", default="[]", help="Answers JSON array.")
    questionnaire.add_argument("--no-llm", action="store_true", help="Skip Kimi and use local fallback scoring.")

    args = parser.parse_args(argv)
    store = MemoryStore(args.memory_path) if args.memory_path else MemoryStore()
    orchestrator = Orchestrator(store)

    try:
        if args.command == "orchestrate":
            result = orchestrator.run(_load_json_arg(args.payload))
        elif args.command == "training":
            result = run_training_check(
                store,
                {
                    "user_id": args.user_id,
                    "entry": "training",
                    "scenario": args.scenario,
                    "message": args.message,
                    "use_llm": args.use_llm,
                    "form_data": _loads_json(args.form_json, expected=dict),
                }
            )
        elif args.command == "assessment":
            result = orchestrator.run(
                {
                    "user_id": args.user_id,
                    "entry": "assessment",
                    "answers": _loads_json(args.answers_json, expected=list),
                }
            )
        elif args.command == "review":
            result = orchestrator.run(
                {
                    "user_id": args.user_id,
                    "entry": "review",
                    "message": args.message,
                    "self_reflection": args.self_reflection,
                    "trade_record": _loads_json(args.trade_json, expected=dict),
                    "trade_table": _loads_json(args.trade_table_json, expected=list) if args.trade_table_json else [],
                    "use_llm": args.use_llm,
                }
            )
        elif args.command == "research":
            result = broker_report_search(args.query, limit=args.limit)
        elif args.command == "questionnaires":
            result = {"questionnaires": list_questionnaires()}
        elif args.command == "questionnaire":
            if args.action == "show":
                result = get_questionnaire(args.id)
            else:
                result = run_questionnaire_assessment(
                    store=store,
                    user_id=args.user_id,
                    questionnaire_id=args.id,
                    answers=_loads_json(args.answers_json, expected=list),
                    use_llm=not args.no_llm,
                )
        else:
            parser.error(f"Unsupported command: {args.command}")
    except QuestionnaireAnswerValidationError as exc:
        print(json.dumps({"error": "invalid_questionnaire_answers", "detail": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _load_json_arg(value: str) -> dict[str, Any]:
    if value.startswith("@"):
        path = Path(value[1:])
        return _loads_json(path.read_text(encoding="utf-8"), expected=dict)
    return _loads_json(value, expected=dict)


def _loads_json(value: str, expected: type) -> Any:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {exc}") from exc
    if not isinstance(parsed, expected):
        raise SystemExit(f"Expected JSON {expected.__name__}, got {type(parsed).__name__}")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

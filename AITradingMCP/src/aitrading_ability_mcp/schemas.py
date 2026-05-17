from __future__ import annotations

from typing import Any


QUESTIONNAIRE_IDS = [
    "full_assessment",
    "trading_cognition",
    "analysis_framework",
    "risk_control",
    "position_management",
    "trade_plan",
    "emotion_discipline",
    "review_ability",
    "scenario_maturity",
]

TRAINING_SCENARIOS = ["buy", "hold", "add", "reduce", "loss", "chase", "check"]

MEMORY_COLLECTIONS = [
    "all",
    "user_profiles",
    "session_memories",
    "training_tasks",
    "trade_records",
    "assessment_results",
    "questionnaire_results",
    "review_reports",
    "tool_call_logs",
    "compliance_logs",
    "research_reports",
]

SESSION_TYPES = ["assessment", "training", "review", "questionnaire_assessment"]
PROFILE_SOURCE_PREFERENCES = ["latest", "full_assessment", "any_questionnaire", "compact_profile"]


def empty_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": {}}


def memory_snapshot_schema() -> dict[str, Any]:
    return strict_object(
        {
            "collection": {
                "type": "string",
                "enum": MEMORY_COLLECTIONS,
                "default": "all",
                "description": "Collection to return. Use 'all' for the full backend memory snapshot.",
            },
            "user_id": {
                "type": "string",
                "description": "Optional user id used to filter user-scoped array collections.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 20,
                "description": "Maximum rows returned for array collections after filtering.",
            },
        }
    )


def user_profile_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {
                "type": "string",
                "description": "Client-managed user id whose capability profile should be returned.",
            }
        },
        required=["user_id"],
    )


def extract_user_profile_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {
                "type": "string",
                "description": (
                    "Optional client-managed user id. Agents may omit this in a single-user local setup; "
                    "the MCP server will use AITRADING_MCP_DEFAULT_USER_ID or infer the only user in backend memory."
                ),
            },
            "preferred_source": {
                "type": "string",
                "enum": PROFILE_SOURCE_PREFERENCES,
                "default": "latest",
                "description": (
                    "Profile source priority. 'latest' prefers the richest generated profile; "
                    "'full_assessment' requires a full questionnaire result when available; "
                    "'any_questionnaire' accepts any questionnaire profile; 'compact_profile' reads only user_profiles[user_id]."
                ),
            },
            "include_evidence": {
                "type": "boolean",
                "default": True,
                "description": "Include questionnaire evidence when the selected profile source contains it.",
            },
            "include_history": {
                "type": "boolean",
                "default": True,
                "description": "Include recent session memories and repeated risk tags as profile context.",
            },
            "history_limit": {
                "type": "integer",
                "minimum": 0,
                "maximum": 20,
                "default": 5,
                "description": "Maximum recent user memories to include when include_history is true.",
            },
            "include_raw": {
                "type": "boolean",
                "default": False,
                "description": "Attach the raw backend source record used to build the extracted profile.",
            },
        },
    )


def profile_sources_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {
                "type": "string",
                "description": (
                    "Optional client-managed user id. Agents may omit this in a single-user local setup; "
                    "the MCP server will use AITRADING_MCP_DEFAULT_USER_ID or infer the only user in backend memory."
                ),
            },
            "include_raw": {
                "type": "boolean",
                "default": False,
                "description": "Attach raw backend records for diagnostics. Defaults to false to keep context small.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Maximum records to return per profile source collection.",
            },
        },
    )


def raw_user_profile_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {
                "type": "string",
                "description": (
                    "Optional client-managed user id. Agents may omit this in a single-user local setup; "
                    "the MCP server will use AITRADING_MCP_DEFAULT_USER_ID or infer the only user in backend memory."
                ),
            },
            "include_assessment_results": {
                "type": "boolean",
                "default": True,
                "description": "Include latest assessment_results records for this user.",
            },
            "include_questionnaire_results": {
                "type": "boolean",
                "default": True,
                "description": "Include latest questionnaire_results records for this user.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 5,
                "description": "Maximum generated profile records per collection.",
            },
        },
    )


def search_memories_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {
                "type": "string",
                "description": (
                    "Optional client-managed user id. Agents may omit this in a single-user local setup; "
                    "the MCP server will use AITRADING_MCP_DEFAULT_USER_ID or infer the only user in backend memory."
                ),
            },
            "query": {
                "type": "string",
                "default": "",
                "description": "Optional substring query matched against summary, decision_pattern, and tags.",
            },
            "session_type": {
                "type": "string",
                "enum": SESSION_TYPES,
                "description": "Optional memory type filter.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Optional tags that must appear in a memory record.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 5,
                "description": "Maximum number of matching memories to return.",
            },
        },
    )


def questionnaire_id_schema() -> dict[str, Any]:
    return strict_object(
        {
            "questionnaire_id": {
                "type": "string",
                "enum": QUESTIONNAIRE_IDS,
                "description": "Questionnaire id to load.",
            }
        },
        required=["questionnaire_id"],
    )


def questionnaire_submit_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {"type": "string", "default": "demo_user", "description": "Client-managed user id."},
            "questionnaire_id": {
                "type": "string",
                "enum": QUESTIONNAIRE_IDS,
                "description": "Questionnaire id. Answers must cover all questions in this questionnaire exactly once.",
            },
            "answers": {
                "type": "array",
                "description": "Every item must include question_id and answer. Empty answers are allowed; missing question ids are rejected by the backend.",
                "items": strict_object(
                    {
                        "question_id": {"type": "string", "description": "Question id from the selected questionnaire."},
                        "answer": {"type": ["string", "null"], "description": "User answer; null is normalized by the backend."},
                    },
                    required=["question_id", "answer"],
                ),
            },
            "use_llm": {
                "type": "boolean",
                "default": True,
                "description": "When true, backend may call its configured OpenAI-compatible model; failure falls back to heuristic scoring.",
            },
        },
        required=["questionnaire_id", "answers"],
    )


def quick_assessment_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {"type": "string", "default": "demo_user", "description": "Client-managed user id."},
            "answers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Free-text answers used by the heuristic capability assessment path.",
            },
            "trade_records": {
                "type": "array",
                "items": trade_record_schema(additional=True),
                "default": [],
                "description": "Optional historical trade records to include in the quick assessment.",
            },
        },
        required=["answers"],
    )


def behavior_plan_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {"type": "string", "default": "demo_user", "description": "Client-managed user id."},
            "scenario": {
                "type": "string",
                "enum": TRAINING_SCENARIOS,
                "default": "check",
                "description": "Behavior training scenario. It classifies the training context only and is not a buy/sell instruction.",
            },
            "message": {
                "type": "string",
                "default": "",
                "description": "Free-text user context about the plan, uncertainty, or emotion.",
            },
            "trade_plan": trade_plan_schema(),
            "use_llm": {
                "type": "boolean",
                "default": False,
                "description": "When true, backend may ask its configured LLM to refine wording; failure falls back to heuristic feedback.",
            },
            "research_limit": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "default": 5,
                "description": "Maximum public research background items to fold into the training report.",
            },
        },
        required=["trade_plan"],
    )


def review_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {"type": "string", "default": "demo_user", "description": "Client-managed user id."},
            "self_reflection": {"type": "string", "default": "", "description": "User's own post-trade reflection."},
            "trade_record": trade_record_schema(additional=False),
            "use_llm": {
                "type": "boolean",
                "default": False,
                "description": "When true, backend may ask its configured LLM to refine review wording; failure falls back to heuristic feedback.",
            },
        },
        required=["trade_record"],
    )


def research_schema() -> dict[str, Any]:
    return strict_object(
        {
            "query": {
                "type": "string",
                "description": "Public research background query, such as '300059 东方财富 研报'. This never requests recommendations or signals.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 5,
                "description": "Maximum number of public report metadata records to return.",
            },
        },
        required=["query"],
    )


def orchestrate_schema() -> dict[str, Any]:
    return strict_object(
        {
            "user_id": {"type": "string", "default": "demo_user", "description": "Client-managed user id."},
            "message": {
                "type": "string",
                "description": "Free-text message. Backend classifies it into assessment, training, or review.",
            },
            "entry": {
                "type": "string",
                "enum": ["assessment", "training", "review", "demo"],
                "description": "Optional explicit entry. Omit to let the backend infer from message keywords.",
            },
            "scenario": {
                "type": "string",
                "enum": TRAINING_SCENARIOS,
                "description": "Optional behavior training scenario when entry is training.",
            },
            "form_data": {
                "type": "object",
                "additionalProperties": True,
                "description": "Optional raw form payload accepted by the backend for demo or orchestration flows.",
            },
            "use_llm": {"type": "boolean", "default": False, "description": "Optional LLM wording flag for supported backend paths."},
        },
        required=["message"],
    )


def trade_plan_schema() -> dict[str, Any]:
    return strict_object(
        {
            "stock": {"type": "string", "description": "Optional stock name/code used only for background research lookup."},
            "position": {"type": ["number", "string"], "description": "Current position percentage."},
            "buy_price": {"type": ["number", "string"], "description": "Reference entry price supplied by the user."},
            "add_ratio": {"type": ["number", "string"], "description": "Planned add/reduce percentage, if relevant."},
            "reason": {"type": "string", "description": "Entry or holding reason."},
            "stop_loss": {"type": "string", "description": "Stop-loss or failure condition. Empty values are treated as plan risk."},
            "max_loss": {"type": "string", "description": "Maximum acceptable loss."},
            "holding_period": {"type": "string", "description": "Expected holding period."},
            "emotion": {"type": "string", "description": "Current emotional state."},
            "invalid_condition": {"type": "string", "description": "Condition proving the plan invalid."},
        },
        required=["reason", "stop_loss", "max_loss", "holding_period", "emotion"],
    )


def trade_record_schema(additional: bool = False) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": additional,
        "properties": {
            "stock": {"type": "string", "description": "Instrument name/code from the completed trade."},
            "buy_time": {"type": "string", "description": "Buy time, if known."},
            "sell_time": {"type": "string", "description": "Sell time, if known."},
            "buy_price": {"type": ["number", "string"], "description": "Buy price."},
            "sell_price": {"type": ["number", "string"], "description": "Sell price."},
            "position": {"type": ["number", "string"], "description": "Position percentage."},
            "buy_reason": {"type": "string", "description": "Reason documented before buying."},
            "sell_reason": {"type": "string", "description": "Reason documented before selling."},
            "stop_loss_plan": {"type": "string", "description": "Predefined stop-loss or failure condition."},
            "followed_plan": {"type": "string", "description": "Whether the user followed the original plan, e.g. 是/否/yes/no."},
            "had_stop_loss": {"type": "string", "description": "Whether a stop-loss existed."},
            "changed_plan": {"type": "string", "description": "Whether the user changed the plan during the trade."},
            "holding_period": {"type": "string", "description": "Actual or expected holding period."},
            "emotion": {"type": "string", "description": "Emotional state during the trade."},
            "result": {"type": "string", "description": "Outcome summary, e.g. 亏损 -6.2%."},
            "self_summary": {"type": "string", "description": "User-written trade summary."},
        },
    }


def strict_object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def apply_defaults(schema: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for key, prop in schema.get("properties", {}).items():
        if key not in result and "default" in prop:
            default = prop["default"]
            result[key] = list(default) if isinstance(default, list) else default
    return result


def validate(schema: dict[str, Any], value: Any, path: str = "arguments") -> list[str]:
    errors: list[str] = []
    _validate(schema, value, path, errors)
    return errors


def _validate(schema: dict[str, Any], value: Any, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected and not _matches_type(expected, value):
        errors.append(f"{path} must be {expected}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']}")
        return

    if isinstance(value, dict) and schema.get("type") == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key} is not allowed")
        for key, item in value.items():
            if key in properties:
                _validate(properties[key], item, f"{path}.{key}", errors)
        return

    if isinstance(value, list) and schema.get("type") == "array":
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            _validate(item_schema, item, f"{path}[{index}]", errors)
        return

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} must be <= {schema['maximum']}")


def _matches_type(expected: Any, value: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(item, value) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True

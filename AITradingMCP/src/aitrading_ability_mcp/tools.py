from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from .client import AITradingClient, BackendError
from . import schemas


COMPLIANCE_NOTICE = "本系统仅用于投资教育与交易能力训练，不构成任何投资建议、个股推荐或买卖信号。"

Handler = Callable[[AITradingClient, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    endpoint: str
    writes_memory: bool
    handler: Handler

    def manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


DEFAULT_TOOL_NAMES = {
    "aitrading_health_check",
    "aitrading_extract_user_profile",
    "aitrading_list_user_profile_sources",
    "aitrading_get_user_profile_raw",
    "aitrading_search_user_profile_memories",
}


def list_tools() -> list[dict[str, Any]]:
    return [tool.manifest() for tool in _active_tools().values()]


def call_tool(client: AITradingClient, name: str, arguments: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    tools = _active_tools()
    tool = tools.get(name)
    if tool is None:
        if name in TOOLS:
            return True, _error(
                "tool_disabled",
                f"Tool is disabled by default: {name}",
                details={
                    "known_tools": sorted(tools),
                    "enable_write_tools": "Set AITRADING_MCP_ENABLE_WRITE_TOOLS=true to expose write/admin tools.",
                },
            )
        return True, _error("validation_error", f"Unknown tool: {name}", details={"known_tools": sorted(tools)})

    raw_args = arguments or {}
    if not isinstance(raw_args, dict):
        return True, _error("validation_error", "Tool arguments must be a JSON object")

    args = schemas.apply_defaults(tool.input_schema, raw_args)
    validation_errors = schemas.validate(tool.input_schema, args)
    if validation_errors:
        return True, _error("validation_error", "Invalid tool arguments", details={"errors": validation_errors})

    try:
        data = tool.handler(client, args)
    except BackendError as exc:
        error_type = "unavailable" if exc.status_code is None else "backend_error"
        return True, _error(error_type, str(exc), status_code=exc.status_code, details=exc.details)
    except Exception as exc:
        return True, _error("internal_error", f"{type(exc).__name__}: {exc}")

    return False, _ok(tool, data)


def _active_tools() -> dict[str, Tool]:
    if _write_tools_enabled():
        return TOOLS
    return {name: TOOLS[name] for name in TOOLS if name in DEFAULT_TOOL_NAMES}


def _write_tools_enabled() -> bool:
    return os.getenv("AITRADING_MCP_ENABLE_WRITE_TOOLS", "").strip().lower() in {"1", "true", "yes", "on"}


def _get_health(client: AITradingClient, _args: dict[str, Any]) -> dict[str, Any]:
    return client.get("/health")


def _get_memory_snapshot(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    collection = args.get("collection", "all")
    user_id = args.get("user_id")
    limit = int(args.get("limit", 20))
    if collection == "all":
        if user_id:
            return {key: _filter_collection(key, value, user_id, limit) for key, value in snapshot.items()}
        return snapshot
    value = snapshot.get(collection, {} if collection == "user_profiles" else [])
    return {collection: _filter_collection(collection, value, user_id, limit)}


def _get_user_profile(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    user_id = args["user_id"]
    profile = snapshot.get("user_profiles", {}).get(user_id)
    return {"exists": profile is not None, "user_id": user_id, "profile": profile}


def _extract_user_profile(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    resolution = _resolve_user_id(snapshot, args.get("user_id"))
    if resolution["status"] != "resolved":
        return _user_resolution_payload(resolution, profile_status=resolution["status"])
    user_id = resolution["user_id"]
    preferred_source = args.get("preferred_source", "latest")
    source = _select_profile_source(snapshot, user_id, preferred_source)
    history = None
    if args.get("include_history", True):
        history = _build_history_context(snapshot, user_id, int(args.get("history_limit", 5)))

    if source is None:
        return {
            "user_id": user_id,
            "profile_status": "not_found",
            "user_resolution": resolution,
            "source": None,
            "profile": None,
            "history": history,
            "selection_reason": "No generated questionnaire, assessment, or compact user profile exists for this user.",
        }

    profile = _normalize_profile(source, include_evidence=args.get("include_evidence", True))
    result = {
        "user_id": user_id,
        "profile_status": source["status"],
        "user_resolution": resolution,
        "source": _source_summary(source),
        "profile": profile,
        "history": history,
        "selection_reason": source["selection_reason"],
    }
    if args.get("include_raw", False):
        result["raw_source"] = source["record"]
    return result


def _list_user_profile_sources(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    resolution = _resolve_user_id(snapshot, args.get("user_id"))
    if resolution["status"] != "resolved":
        return _user_resolution_payload(resolution, profile_status=resolution["status"])
    user_id = resolution["user_id"]
    limit = int(args.get("limit", 10))
    include_raw = args.get("include_raw", False)
    compact = _compact_profile_source(snapshot, user_id)
    questionnaire = _questionnaire_profile_sources(snapshot, user_id)[:limit]
    assessment = _assessment_profile_sources(snapshot, user_id)[:limit]
    payload: dict[str, Any] = {
        "user_id": user_id,
        "user_resolution": resolution,
        "counts": {
            "compact_profile": 1 if compact else 0,
            "questionnaire_results": len(_questionnaire_profile_sources(snapshot, user_id)),
            "assessment_results": len(_assessment_profile_sources(snapshot, user_id)),
        },
        "compact_profile": _source_summary(compact) if compact else None,
        "questionnaire_results": [_source_summary(source) for source in questionnaire],
        "assessment_results": [_source_summary(source) for source in assessment],
    }
    if include_raw:
        payload["raw"] = {
            "compact_profile": compact["record"] if compact else None,
            "questionnaire_results": [source["record"] for source in questionnaire],
            "assessment_results": [source["record"] for source in assessment],
        }
    return payload


def _get_user_profile_raw(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    resolution = _resolve_user_id(snapshot, args.get("user_id"))
    if resolution["status"] != "resolved":
        return _user_resolution_payload(resolution, profile_status=resolution["status"])
    user_id = resolution["user_id"]
    limit = int(args.get("limit", 5))
    payload = {
        "user_id": user_id,
        "user_resolution": resolution,
        "compact_profile": snapshot.get("user_profiles", {}).get(user_id),
    }
    if args.get("include_questionnaire_results", True):
        payload["questionnaire_results"] = _user_records(snapshot, "questionnaire_results", user_id)[:limit]
    if args.get("include_assessment_results", True):
        payload["assessment_results"] = _user_records(snapshot, "assessment_results", user_id)[:limit]
    return payload


def _search_user_memories(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    snapshot = client.get("/api/memory")
    resolution = _resolve_user_id(snapshot, args.get("user_id"))
    if resolution["status"] != "resolved":
        return _user_resolution_payload(resolution, profile_status=resolution["status"])
    user_id = resolution["user_id"]
    query = args.get("query", "")
    query_tokens = [token for token in query.replace(",", " ").replace("，", " ").split() if token]
    session_type = args.get("session_type")
    required_tags = set(args.get("tags") or [])
    limit = int(args.get("limit", 5))
    memories = []
    for item in snapshot.get("session_memories", []):
        if item.get("user_id") != user_id:
            continue
        if session_type and item.get("session_type") != session_type:
            continue
        tags = set(item.get("tags") or [])
        if required_tags and not required_tags.issubset(tags):
            continue
        haystack = " ".join([item.get("summary", ""), item.get("decision_pattern", ""), " ".join(tags)])
        if query_tokens and not any(token in haystack for token in query_tokens):
            continue
        memories.append(item)
    return {"user_id": user_id, "user_resolution": resolution, "count": len(memories[:limit]), "memories": memories[:limit]}


def _search_user_profile_memories(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    result = _search_user_memories(client, args)
    repeated_tags = _count_tags(result["memories"])
    result["repeated_tags"] = repeated_tags
    result["profile_context_note"] = (
        "These memories provide behavioral context for the generated user profile; "
        "they are not a substitute for questionnaire_results or user_profiles."
    )
    return result


def _list_questionnaires(client: AITradingClient, _args: dict[str, Any]) -> dict[str, Any]:
    return client.get("/api/questionnaires")


def _get_questionnaire(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    return client.get(f"/api/questionnaires/{args['questionnaire_id']}")


def _submit_questionnaire(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    questionnaire_id = args["questionnaire_id"]
    payload = {
        "user_id": args.get("user_id", "demo_user"),
        "answers": args["answers"],
        "use_llm": args.get("use_llm", True),
    }
    return client.post(f"/api/questionnaires/{questionnaire_id}/submit", payload)


def _run_quick_assessment(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "user_id": args.get("user_id", "demo_user"),
        "answers": args["answers"],
        "trade_records": args.get("trade_records", []),
    }
    return client.post("/api/assessment/run", payload)


def _check_behavior_plan(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "user_id": args.get("user_id", "demo_user"),
        "scenario": args.get("scenario", "check"),
        "message": args.get("message", ""),
        "trade_plan": args["trade_plan"],
        "use_llm": args.get("use_llm", False),
        "research_limit": args.get("research_limit", 5),
    }
    return client.post("/api/training/check", payload)


def _review_trade_record(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "user_id": args.get("user_id", "demo_user"),
        "self_reflection": args.get("self_reflection", ""),
        "trade_record": args["trade_record"],
        "use_llm": args.get("use_llm", False),
    }
    return client.post("/api/review/run", payload)


def _search_public_research(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    return client.post("/api/research/search", {"query": args["query"], "limit": args.get("limit", 5)})


def _orchestrate_message(client: AITradingClient, args: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "user_id": args.get("user_id", "demo_user"),
        "message": args["message"],
        "use_llm": args.get("use_llm", False),
    }
    for key in ("entry", "scenario", "form_data"):
        if key in args:
            payload[key] = args[key]
    return client.post("/api/orchestrate", payload)


def _select_profile_source(snapshot: dict[str, Any], user_id: str, preferred_source: str) -> dict[str, Any] | None:
    compact = _compact_profile_source(snapshot, user_id)
    questionnaires = _questionnaire_profile_sources(snapshot, user_id)
    assessments = _assessment_profile_sources(snapshot, user_id)
    full = [source for source in questionnaires if source["questionnaire_id"] == "full_assessment"]

    if preferred_source == "compact_profile":
        if compact:
            compact["selection_reason"] = "Selected compact user_profiles[user_id] because preferred_source=compact_profile."
        return compact

    if preferred_source == "full_assessment":
        if full:
            full[0]["selection_reason"] = "Selected latest full_assessment questionnaire profile."
            return full[0]
        fallback = questionnaires[0] if questionnaires else assessments[0] if assessments else compact
        if fallback:
            fallback["selection_reason"] = "No full_assessment result found; fell back to the richest available generated profile."
        return fallback

    if preferred_source == "any_questionnaire":
        if questionnaires:
            questionnaires[0]["selection_reason"] = "Selected latest questionnaire profile."
            return questionnaires[0]
        fallback = assessments[0] if assessments else compact
        if fallback:
            fallback["selection_reason"] = "No questionnaire result found; fell back to assessment or compact profile."
        return fallback

    if full:
        full[0]["selection_reason"] = "Selected latest full_assessment result as the richest generated profile."
        return full[0]
    if questionnaires:
        questionnaires[0]["selection_reason"] = "Selected latest questionnaire result because no full_assessment result exists."
        return questionnaires[0]
    if assessments:
        assessments[0]["selection_reason"] = "Selected latest assessment result because no questionnaire result exists."
        return assessments[0]
    if compact:
        compact["selection_reason"] = "Selected compact profile because no generated assessment record exists."
    return compact


def _resolve_user_id(snapshot: dict[str, Any], explicit_user_id: Any = None) -> dict[str, Any]:
    explicit = str(explicit_user_id or "").strip()
    if explicit:
        return {"status": "resolved", "user_id": explicit, "source": "argument", "candidates": _collect_user_ids(snapshot)}

    configured = os.getenv("AITRADING_MCP_DEFAULT_USER_ID", "").strip()
    if configured:
        return {"status": "resolved", "user_id": configured, "source": "env", "candidates": _collect_user_ids(snapshot)}

    candidates = _collect_user_ids(snapshot)
    if len(candidates) == 1:
        return {"status": "resolved", "user_id": candidates[0], "source": "single_user_memory", "candidates": candidates}
    if len(candidates) > 1:
        return {"status": "ambiguous_user", "user_id": None, "source": "memory", "candidates": candidates}
    return {"status": "no_user_found", "user_id": None, "source": "memory", "candidates": []}


def _collect_user_ids(snapshot: dict[str, Any]) -> list[str]:
    user_ids: set[str] = set()
    profiles = snapshot.get("user_profiles", {})
    if isinstance(profiles, dict):
        user_ids.update(str(user_id) for user_id in profiles if str(user_id).strip())

    for collection in (
        "questionnaire_results",
        "assessment_results",
        "session_memories",
        "review_reports",
        "training_tasks",
        "trade_records",
        "tool_call_logs",
    ):
        for item in snapshot.get(collection, []):
            if isinstance(item, dict) and item.get("user_id"):
                user_ids.add(str(item["user_id"]))
    return sorted(user_ids)


def _user_resolution_payload(resolution: dict[str, Any], profile_status: str) -> dict[str, Any]:
    if profile_status == "ambiguous_user":
        message = "Multiple local users were found. The agent should ask which user profile to use, then retry with user_id."
    else:
        message = (
            "No local user memory was found. The user may need to complete an assessment in the frontend first, "
            "or configure AITRADING_MCP_DEFAULT_USER_ID."
        )
    return {
        "user_id": resolution.get("user_id"),
        "profile_status": profile_status,
        "user_resolution": resolution,
        "source": None,
        "profile": None,
        "history": None,
        "selection_reason": message,
    }


def _compact_profile_source(snapshot: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    profile = snapshot.get("user_profiles", {}).get(user_id)
    if not isinstance(profile, dict):
        return None
    return {
        "kind": "compact_profile",
        "status": "compact_profile",
        "record": profile,
        "report": profile,
        "report_id": None,
        "questionnaire_id": None,
        "created_at": profile.get("updated_at", ""),
        "selection_reason": "",
    }


def _questionnaire_profile_sources(snapshot: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    sources = []
    for record in _user_records(snapshot, "questionnaire_results", user_id):
        report = record.get("report") if isinstance(record.get("report"), dict) else {}
        if not report:
            continue
        sources.append(
            {
                "kind": "questionnaire_results",
                "status": "questionnaire_profile",
                "record": record,
                "report": report,
                "report_id": report.get("report_id") or record.get("result_id"),
                "questionnaire_id": record.get("questionnaire_id") or report.get("questionnaire_id"),
                "created_at": record.get("created_at") or report.get("created_at", ""),
                "selection_reason": "",
            }
        )
    return sources


def _assessment_profile_sources(snapshot: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    sources = []
    for record in _user_records(snapshot, "assessment_results", user_id):
        if not isinstance(record, dict):
            continue
        status = "questionnaire_profile" if record.get("schema_version") == "questionnaire_profile.v1" else "assessment_profile"
        sources.append(
            {
                "kind": "assessment_results",
                "status": status,
                "record": record,
                "report": record,
                "report_id": record.get("report_id") or record.get("result_id"),
                "questionnaire_id": record.get("questionnaire_id"),
                "created_at": record.get("created_at", ""),
                "selection_reason": "",
            }
        )
    return sources


def _user_records(snapshot: dict[str, Any], collection: str, user_id: str) -> list[dict[str, Any]]:
    return [
        item
        for item in snapshot.get(collection, [])
        if isinstance(item, dict) and item.get("user_id") == user_id
    ]


def _source_summary(source: dict[str, Any] | None) -> dict[str, Any] | None:
    if not source:
        return None
    report = source.get("report") or {}
    evidence = report.get("evidence") if isinstance(report.get("evidence"), list) else []
    return {
        "kind": source.get("kind"),
        "status": source.get("status"),
        "questionnaire_id": source.get("questionnaire_id"),
        "report_id": source.get("report_id"),
        "created_at": source.get("created_at"),
        "schema_version": report.get("schema_version"),
        "trader_type": report.get("trader_type"),
        "total_score": report.get("total_score"),
        "risk_level": report.get("risk_level"),
        "has_profile_summary": bool(report.get("profile_summary") or report.get("summary")),
        "evidence_count": len(evidence),
    }


def _normalize_profile(source: dict[str, Any], include_evidence: bool) -> dict[str, Any]:
    report = source["report"]
    summary = report.get("profile_summary") or report.get("summary") or _compact_profile_summary(report)
    profile = {
        "trader_type": report.get("trader_type"),
        "total_score": report.get("total_score"),
        "dimension_scores": report.get("dimension_scores") or {},
        "risk_level": report.get("risk_level"),
        "weaknesses": report.get("weaknesses") or [],
        "risk_tags": report.get("risk_tags") or [],
        "profile_summary": summary,
        "next_training_focus": report.get("next_training_focus") or [],
        "recommended_tasks": report.get("recommended_tasks") or [],
        "updated_at": report.get("updated_at") or report.get("created_at") or source.get("created_at"),
    }
    if include_evidence:
        profile["evidence"] = report.get("evidence") if isinstance(report.get("evidence"), list) else []
    return profile


def _compact_profile_summary(profile: dict[str, Any]) -> str:
    trader_type = profile.get("trader_type") or "未知类型"
    total_score = profile.get("total_score")
    weaknesses = "、".join(profile.get("weaknesses") or [])
    risk_tags = "、".join(profile.get("risk_tags") or [])
    parts = [f"当前画像为{trader_type}"]
    if total_score is not None:
        parts.append(f"综合得分 {total_score}")
    if weaknesses:
        parts.append(f"主要弱项：{weaknesses}")
    if risk_tags:
        parts.append(f"风险标签：{risk_tags}")
    return "，".join(parts) + "。"


def _build_history_context(snapshot: dict[str, Any], user_id: str, limit: int) -> dict[str, Any]:
    if limit <= 0:
        return {"recent_memories": [], "repeated_tags": []}
    memories = _user_records(snapshot, "session_memories", user_id)[:limit]
    return {"recent_memories": memories, "repeated_tags": _count_tags(memories)}


def _count_tags(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for record in records:
        for tag in record.get("tags") or []:
            counts[str(tag)] = counts.get(str(tag), 0) + 1
    return [
        {"tag": tag, "count": count}
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _filter_collection(collection: str, value: Any, user_id: str | None, limit: int) -> Any:
    if collection == "user_profiles":
        if not user_id:
            return value
        profile = value.get(user_id) if isinstance(value, dict) else None
        return {user_id: profile} if profile is not None else {}
    if not isinstance(value, list):
        return value
    rows = value
    if user_id:
        rows = [item for item in rows if isinstance(item, dict) and item.get("user_id") == user_id]
    return rows[:limit]


def _ok(tool: Tool, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "source_endpoint": tool.endpoint,
        "writes_memory": tool.writes_memory,
        "compliance_notice": COMPLIANCE_NOTICE,
        "data": data,
    }


def _error(
    error_type: str,
    message: str,
    status_code: int | None = None,
    details: Any = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "error_type": error_type,
        "message": message,
        "compliance_notice": COMPLIANCE_NOTICE,
    }
    if status_code is not None:
        payload["status_code"] = status_code
    if details is not None:
        payload["details"] = details
    return payload


TOOLS: dict[str, Tool] = {
    "aitrading_health_check": Tool(
        name="aitrading_health_check",
        description=(
            "Check whether the AITrading ability-training backend is reachable. "
            "Input: empty object. Returns normalized backend health. "
            "Use before extracting a generated user profile. "
            "Do NOT use for market status or trading readiness; this is only service liveness."
        ),
        input_schema=schemas.empty_schema(),
        endpoint="/health",
        writes_memory=False,
        handler=_get_health,
    ),
    "aitrading_extract_user_profile": Tool(
        name="aitrading_extract_user_profile",
        description=(
            "Extract the generated user capability profile after the user has already completed frontend assessment/testing. "
            "Input: optional user_id plus source preference and history/evidence flags. In a single-user local setup, agents can omit user_id; the server uses AITRADING_MCP_DEFAULT_USER_ID or infers the only user in memory. "
            "Returns a normalized profile assembled from questionnaire_results, assessment_results, user_profiles, and recent session memories. "
            "Use this as the primary agent-facing profile reader. If multiple users exist, ask the user which candidate to use and retry with user_id. "
            "Do NOT use this to administer tests, submit answers, train behavior, review trades, or generate trading recommendations."
        ),
        input_schema=schemas.extract_user_profile_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_extract_user_profile,
    ),
    "aitrading_list_user_profile_sources": Tool(
        name="aitrading_list_user_profile_sources",
        description=(
            "List available generated profile sources for one user without creating new assessments. "
            "Input: optional user_id, optional limit and include_raw. In a single-user local setup, agents can omit user_id. Returns compact profile presence plus questionnaire_results and assessment_results summaries. "
            "Use to debug why a profile was selected or to let an agent choose a source. "
            "Do NOT use this to run or submit an assessment."
        ),
        input_schema=schemas.profile_sources_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_list_user_profile_sources,
    ),
    "aitrading_get_user_profile_raw": Tool(
        name="aitrading_get_user_profile_raw",
        description=(
            "Return raw backend profile records for one user: user_profiles[user_id] plus latest questionnaire_results and assessment_results. "
            "Input: optional user_id, optional inclusion flags and limit. In a single-user local setup, agents can omit user_id. This is a diagnostic/raw companion to aitrading_extract_user_profile. "
            "Use when an agent needs exact backend records. "
            "Do NOT use when a normalized profile is enough; prefer aitrading_extract_user_profile."
        ),
        input_schema=schemas.raw_user_profile_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_get_user_profile_raw,
    ),
    "aitrading_search_user_profile_memories": Tool(
        name="aitrading_search_user_profile_memories",
        description=(
            "Search historical session memories for one user as context around their generated profile. "
            "Input: optional user_id plus query, session_type, tags, and limit. In a single-user local setup, agents can omit user_id. Returns matching memories and repeated tag counts. "
            "Use only as supporting context for profile interpretation. "
            "Do NOT treat memories as a replacement for questionnaire_results or user_profiles."
        ),
        input_schema=schemas.search_memories_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_search_user_profile_memories,
    ),
    "aitrading_get_memory_snapshot": Tool(
        name="aitrading_get_memory_snapshot",
        description=(
            "Read backend memory collections for profiles, session memories, reports, tasks, and tool traces. "
            "Input: optional collection, user_id, and limit. Returns filtered JSON-backed memory. "
            "Use for dashboards, audit trails, or retrieving training history. "
            "Do NOT use to infer buy/sell signals; memory contains education and behavior-training records only."
        ),
        input_schema=schemas.memory_snapshot_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_get_memory_snapshot,
    ),
    "aitrading_get_user_profile": Tool(
        name="aitrading_get_user_profile",
        description=(
            "Read one user's capability profile from AITrading memory. "
            "Input: user_id string. Returns exists flag plus profile with trader_type, total_score, dimensions, risk tags, and weaknesses. "
            "Use when an agent needs the user's training level before feedback. "
            "Do NOT use as investment suitability or financial advice."
        ),
        input_schema=schemas.user_profile_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_get_user_profile,
    ),
    "aitrading_search_user_memories": Tool(
        name="aitrading_search_user_memories",
        description=(
            "Search one user's historical training, assessment, and review memories. "
            "Input: user_id plus optional query, session_type, tags, limit. Returns matching session memory records. "
            "Use to detect repeated behavior patterns before training or review. "
            "Do NOT use for external market research or recommendations."
        ),
        input_schema=schemas.search_memories_schema(),
        endpoint="/api/memory",
        writes_memory=False,
        handler=_search_user_memories,
    ),
    "aitrading_list_questionnaires": Tool(
        name="aitrading_list_questionnaires",
        description=(
            "List available AITrading capability questionnaires. "
            "Input: empty object. Returns full_assessment plus partial diagnostics such as risk_control and review_ability. "
            "Use before asking a user to complete a questionnaire. "
            "Do NOT use for scoring answers; use aitrading_submit_questionnaire_assessment after collecting answers."
        ),
        input_schema=schemas.empty_schema(),
        endpoint="/api/questionnaires",
        writes_memory=False,
        handler=_list_questionnaires,
    ),
    "aitrading_get_questionnaire": Tool(
        name="aitrading_get_questionnaire",
        description=(
            "Fetch one questionnaire definition with questions, dimensions, and rubrics. "
            "Input: questionnaire_id enum. Returns the question list. "
            "Use to render or ask assessment questions. "
            "Do NOT submit answers through this tool; use aitrading_submit_questionnaire_assessment."
        ),
        input_schema=schemas.questionnaire_id_schema(),
        endpoint="/api/questionnaires/{questionnaire_id}",
        writes_memory=False,
        handler=_get_questionnaire,
    ),
    "aitrading_submit_questionnaire_assessment": Tool(
        name="aitrading_submit_questionnaire_assessment",
        description=(
            "Submit completed questionnaire answers and generate a fixed capability profile. "
            "Input: questionnaire_id, user_id, answers, optional use_llm. Answers must cover every question id exactly once. "
            "Returns report, tool_trace, and memory. This writes backend profile, assessment result, and session memory. "
            "Do NOT use for stock picks, price targets, or trading signals."
        ),
        input_schema=schemas.questionnaire_submit_schema(),
        endpoint="/api/questionnaires/{questionnaire_id}/submit",
        writes_memory=True,
        handler=_submit_questionnaire,
    ),
    "aitrading_run_quick_assessment": Tool(
        name="aitrading_run_quick_assessment",
        description=(
            "Run heuristic free-text capability assessment without requiring the full questionnaire. "
            "Input: answers array, optional user_id and trade_records. Returns total score, dimension scores, weaknesses, and next training focus. "
            "This writes backend profile, assessment result, and session memory. "
            "Do NOT use for investment recommendations."
        ),
        input_schema=schemas.quick_assessment_schema(),
        endpoint="/api/assessment/run",
        writes_memory=True,
        handler=_run_quick_assessment,
    ),
    "aitrading_check_behavior_plan": Tool(
        name="aitrading_check_behavior_plan",
        description=(
            "Check a trade plan for training completeness, behavior risk tags, missing fields, and training tasks. "
            "Input: scenario, message, trade_plan, optional research_limit and use_llm. Returns plan_score, rule_status, risk_tags, missing_fields, tasks, and trace. "
            "This writes training tasks and session memory. It never decides whether an asset should be bought, sold, held, added, or reduced."
        ),
        input_schema=schemas.behavior_plan_schema(),
        endpoint="/api/training/check",
        writes_memory=True,
        handler=_check_behavior_plan,
    ),
    "aitrading_review_trade_record": Tool(
        name="aitrading_review_trade_record",
        description=(
            "Review a completed trade record for process quality, mistake attribution, repeated patterns, and new training rules. "
            "Input: trade_record, optional self_reflection, user_id, use_llm. Returns review score, dimensions, mistake_types, root_cause, repeated_patterns, and new_rules. "
            "This writes review report, trade record, and session memory. Do NOT use for next-trade advice."
        ),
        input_schema=schemas.review_schema(),
        endpoint="/api/review/run",
        writes_memory=True,
        handler=_review_trade_record,
    ),
    "aitrading_search_public_research": Tool(
        name="aitrading_search_public_research",
        description=(
            "Search public broker-report background metadata through the backend provider chain. "
            "Input: query and limit. Returns available flag, report metadata, provider, fallback, and errors. "
            "Use only for background context in education/training workflows. "
            "Do NOT interpret missing or positive reports as buy/sell signals."
        ),
        input_schema=schemas.research_schema(),
        endpoint="/api/research/search",
        writes_memory=False,
        handler=_search_public_research,
    ),
    "aitrading_orchestrate_message": Tool(
        name="aitrading_orchestrate_message",
        description=(
            "Developer/demo unified entry that lets the backend classify a free-text message into assessment, training, or review. "
            "Input: message plus optional user_id, entry, scenario, form_data, use_llm. Returns backend report and tool_trace. "
            "This can write session memory depending on the inferred path. Prefer specific tools for production agent workflows."
        ),
        input_schema=schemas.orchestrate_schema(),
        endpoint="/api/orchestrate",
        writes_memory=True,
        handler=_orchestrate_message,
    ),
}

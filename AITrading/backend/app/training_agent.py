from __future__ import annotations

import re
from typing import Any

from .compliance import sanitize_report
from .engines import normalize_training_scenario, training_engine
from .llm_assist import generate_training_conclusion, llm_error_payload
from .memory import MemoryStore
from .models import ToolTrace, new_id, utc_now
from .research import should_search
from .stock_context import build_stock_context_for_prompt, extract_stock_symbol


DECISION_SUPPORT_FIELDS = (
    "decision_support_advice",
    "risk_warnings",
    "missing_research_items",
    "plan_improvement_tasks",
    "pause_conditions",
)

DIRECT_ADVICE_PATTERNS = (
    r"建议你?买入",
    r"建议你?卖出",
    r"建议你?加仓",
    r"建议你?减仓",
    r"可以买",
    r"可以卖",
    r"可以加仓",
    r"可以减仓",
    r"加仓到\s*\d+",
    r"减仓到\s*\d+",
    r"目标价",
    r"稳赚",
    r"必涨",
    r"一定上涨",
    r"买卖信号",
)


def run_training_check(store: MemoryStore, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the behavior-training endpoint directly against training_engine."""
    user_id = payload.get("user_id") or "demo_user"
    message = payload.get("message") or ""
    trade_plan = _trade_plan_from_payload(payload)
    scenario = normalize_training_scenario(payload.get("scenario") or trade_plan.get("scenario"), message)
    intent = _training_intent(scenario)
    trace: list[ToolTrace] = [
        ToolTrace("classify_intent", "success", output_summary={"intent": intent, "entry": "training"})
    ]

    profile = store.get_profile(user_id)
    trace.append(
        ToolTrace(
            "user_profile_get",
            "success",
            input_summary={"user_id": user_id},
            output_summary={"trader_type": profile.trader_type, "total_score": profile.total_score},
        )
    )

    memory_query = _memory_query_text(trade_plan, message)
    memories = store.query_memories(user_id, memory_query, limit=5)
    trace.append(
        ToolTrace(
            "session_memory_query",
            "success",
            input_summary={"query": memory_query, "limit": 5},
            output_summary={"count": len(memories)},
        )
    )

    stock_context = _run_stock_context_import(store, user_id, trade_plan, message, payload, trace)
    report = training_engine(
        profile=profile,
        trade_plan=trade_plan,
        message=message,
        memory_patterns=memories,
        research_context=stock_context.get("reports", []),
        scenario=scenario,
    )
    report["stock_context_used"] = bool(stock_context.get("available"))
    report["stock_context_summary"] = stock_context.get("prompt_context", {})
    trace.append(ToolTrace("training_engine", "success", output_summary={"plan_score": report["plan_score"]}))

    if payload.get("use_llm", True) is not False:
        try:
            llm_report = generate_training_conclusion(
                {
                    "message": message,
                    "scenario": scenario,
                    "trade_plan": trade_plan,
                    "stock_context": stock_context.get("prompt_context", {}),
                },
                report,
            )
            report = _merge_training_llm_fields(report, llm_report)
            trace.append(ToolTrace("training_llm_conclusion", "success"))
        except Exception as exc:
            report.update(llm_error_payload(exc))
            trace.append(ToolTrace("training_llm_conclusion", "fallback", detail=report.get("llm_error", "")))

    report = _ensure_decision_support_fields(report)

    task_records = []
    for content in report.get("training_tasks", []):
        task_records.append(
            store.add_record(
                "training_tasks",
                {
                    "task_id": new_id("task"),
                    "user_id": user_id,
                    "source": "behavior_training",
                    "task_type": "trade_plan_completion",
                    "content": content,
                    "status": "pending",
                    "created_at": utc_now(),
                },
            )
        )
    report["task_ids"] = [item["task_id"] for item in task_records]

    clean_report, compliance = sanitize_report(report)
    trace.append(
        ToolTrace(
            "compliance_guard_check",
            "success" if compliance["passed"] else "rewritten",
            output_summary={"passed": compliance["passed"], "flags": compliance["flagged_patterns"]},
        )
    )
    store.add_record(
        "compliance_logs",
        {
            "compliance_id": new_id("compliance"),
            "user_id": user_id,
            "entry": "training",
            "passed": compliance["passed"],
            "flags": compliance["flagged_patterns"],
            "created_at": utc_now(),
        },
    )

    memory = store.write_memory(
        user_id=user_id,
        session_type="training",
        summary=clean_report.get("summary", ""),
        decision_pattern=_decision_pattern(clean_report),
        tags=clean_report.get("risk_tags") or [],
        report_id=clean_report.get("report_id"),
    )
    trace.append(
        ToolTrace(
            "session_memory_write",
            "success",
            output_summary={"memory_id": memory["memory_id"], "tags": memory["tags"]},
        )
    )

    store.add_record(
        "tool_call_logs",
        {
            "log_id": new_id("trace"),
            "user_id": user_id,
            "entry": "training",
            "intent": intent,
            "tool_trace": [item.to_dict() for item in trace],
            "created_at": utc_now(),
        },
    )

    return {
        "entry": "training",
        "intent": intent,
        "tool_trace": [item.to_dict() for item in trace],
        "report": clean_report,
        "memory_written": True,
        "memory": memory,
    }


def _run_stock_context_import(
    store: MemoryStore,
    user_id: str,
    trade_plan: dict[str, Any],
    message: str,
    payload: dict[str, Any],
    trace: list[ToolTrace],
) -> dict[str, Any]:
    symbol = extract_stock_symbol(trade_plan, message)
    if not symbol or not should_search(trade_plan, message):
        context = {
            "available": False,
            "symbol": symbol,
            "market": payload.get("market") or "A",
            "prompt_context": {
                "usage": "training_context_only",
                "reason": "未触发股票上下文导入。",
            },
            "reports": [],
        }
        trace.append(
            ToolTrace(
                "stock_context_import",
                "skipped",
                output_summary={"symbol": symbol, "reason": context["prompt_context"]["reason"]},
            )
        )
        return context

    context = build_stock_context_for_prompt(
        trade_plan=trade_plan,
        message=message,
        market=payload.get("market") or "A",
        report_limit=int(payload.get("research_limit", 3)),
        news_limit=int(payload.get("news_limit", 5)),
        announcement_limit=int(payload.get("announcement_limit", 5)),
    )
    source_status = context.get("prompt_context", {}).get("source_status", {})
    trace.append(
        ToolTrace(
            "stock_context_import",
            "success" if context.get("available") else "skipped",
            input_summary={"symbol": symbol, "market": payload.get("market") or "A"},
            output_summary={
                "symbol": context.get("symbol", symbol),
                "available": bool(context.get("available")),
                "reports": len(context.get("reports", [])),
                "sources": {
                    key: value.get("ok")
                    for key, value in source_status.items()
                    if isinstance(value, dict)
                },
            },
        )
    )
    if context.get("reports"):
        store.add_record(
            "research_reports",
            {
                "research_id": new_id("research"),
                "user_id": user_id,
                "query": f"{symbol} stock_context",
                "reports": context["reports"],
                "stock_context_summary": context.get("prompt_context", {}),
                "created_at": utc_now(),
            },
        )
    return context


def _trade_plan_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    trade_plan = payload.get("trade_plan") or payload.get("form_data") or {}
    return trade_plan if isinstance(trade_plan, dict) else {}


def _memory_query_text(trade_plan: dict[str, Any], message: str) -> str:
    form_text = " ".join(str(value) for value in trade_plan.values())
    return " ".join([message, form_text]).strip()


def _training_intent(scenario: str) -> str:
    return {
        "add": "add_position_training",
        "reduce": "reduce_position_training",
        "loss": "loss_averaging_training",
        "chase": "chase_training",
        "buy": "pre_trade_training",
        "hold": "hold_position_training",
    }.get(scenario, "behavior_training")


def _decision_pattern(report: dict[str, Any]) -> str:
    tags = report.get("risk_tags") or []
    if tags:
        return "、".join(tags)
    return report.get("training_decision") or "结构化训练记录"


def _merge_training_llm_fields(report: dict[str, Any], llm_report: dict[str, Any]) -> dict[str, Any]:
    """Merge LLM wording while keeping engine scoring and field checks authoritative."""
    merged = dict(report)
    decision = llm_report.get("training_decision")
    if isinstance(decision, str) and _safe_llm_training_text(decision, report):
        merged["training_decision"] = decision.strip()
    summary = llm_report.get("summary")
    if isinstance(summary, str) and _safe_llm_training_text(summary, report):
        merged["summary"] = summary.strip()

    for field in DECISION_SUPPORT_FIELDS:
        items = _safe_llm_training_list(llm_report.get(field), report)
        if items:
            merged[field] = items

    engine_tasks = [str(item) for item in report.get("training_tasks", []) if str(item).strip()]
    llm_tasks = [
        task
        for item in llm_report.get("training_tasks", [])
        if isinstance(item, str)
        for task in [_normalize_training_task(item)]
        if task
    ]
    merged["training_tasks"] = _unique(engine_tasks + llm_tasks)[:6]

    merged["missing_fields"] = report.get("missing_fields", [])
    merged["risk_tags"] = report.get("risk_tags", [])
    merged["plan_score"] = report.get("plan_score", 0)
    merged["rule_status"] = report.get("rule_status", "not_passed")
    merged["llm_used"] = True
    return merged


def _ensure_decision_support_fields(report: dict[str, Any]) -> dict[str, Any]:
    merged = dict(report)
    defaults = _default_decision_support_fields(report)
    for field in DECISION_SUPPORT_FIELDS:
        current = _safe_llm_training_list(merged.get(field), report)
        merged[field] = current or defaults[field]
    return merged


def _default_decision_support_fields(report: dict[str, Any]) -> dict[str, list[str]]:
    missing_fields = [str(item) for item in report.get("missing_fields", []) if str(item).strip()]
    risk_tags = [str(item) for item in report.get("risk_tags", []) if str(item).strip()]
    training_tasks = [str(item) for item in report.get("training_tasks", []) if str(item).strip()]
    stock_context = report.get("stock_context_summary") if isinstance(report.get("stock_context_summary"), dict) else {}

    if missing_fields:
        advice = [f"先补全{'、'.join(missing_fields)}，再进入下一步计划检查。"]
    elif report.get("rule_status") == "passed":
        advice = ["计划关键字段已完整，下一步重点核对买入理由、风险边界与公开背景是否相互支持。"]
    else:
        advice = ["先处理当前训练任务中的行为风险，再进入下一步计划检查。"]

    risk_warnings = [_risk_warning_for_tag(tag) for tag in risk_tags]
    if not risk_warnings:
        risk_warnings = ["暂无高风险标签，仍需按已写明的风险边界检查执行前条件。"]

    missing_research_items = _missing_research_items_from_stock_context(stock_context)
    if not missing_research_items:
        missing_research_items = ["核对最新行情、公告、新闻和研报摘要，确认买入理由不是单一消息或短期波动驱动。"]

    plan_improvement_tasks = training_tasks or ["写出至少一条不交易条件，并在交易后记录是否遵守。"]
    pause_conditions = [
        "触发已写明的风险边界时，暂停本次计划并记录触发原因。",
        "如果买入理由无法被公开资料或价格行为验证，暂停本次计划并补充研究。",
    ]
    if risk_tags:
        pause_conditions.append(f"当{risk_tags[0]}风险继续升高且无法被计划约束时，暂停本次计划。")

    return {
        "decision_support_advice": advice[:3],
        "risk_warnings": _unique(risk_warnings)[:4],
        "missing_research_items": _unique(missing_research_items)[:4],
        "plan_improvement_tasks": _unique(plan_improvement_tasks)[:4],
        "pause_conditions": _unique(pause_conditions)[:4],
    }


def _risk_warning_for_tag(tag: str) -> str:
    warnings = {
        "追涨": "识别到追涨风险，需确认买入理由不是由短期涨幅或踏空情绪触发。",
        "消息驱动": "识别到消息驱动风险，需核对公告、新闻来源和可持续证据。",
        "止损缺失": "识别到风险边界不足，需先写明判断错误时的处理方式。",
        "仓位偏高": "识别到仓位偏高风险，需核对计划仓位是否匹配账户承受能力。",
        "补仓冲动": "识别到补仓冲动风险，需区分计划内加仓条件和亏损后的情绪反应。",
        "报复性交易": "识别到报复性交易风险，需先暂停并复盘亏损后的操作冲动。",
        "计划缺失": "识别到计划缺失风险，需补全关键字段后再进行计划检查。",
    }
    return warnings.get(tag, f"识别到{tag}风险，需写出具体证据和约束条件。")


def _missing_research_items_from_stock_context(stock_context: dict[str, Any]) -> list[str]:
    source_status = stock_context.get("source_status") if isinstance(stock_context.get("source_status"), dict) else {}
    labels = {
        "quote": "实时行情",
        "kline": "近期K线与波动",
        "announcements": "公司公告",
        "news": "相关新闻",
        "company_profile": "公司资料",
        "reports": "研报摘要",
    }
    missing = [
        label
        for key, label in labels.items()
        if isinstance(source_status.get(key), dict) and not source_status[key].get("ok")
    ]
    if missing:
        return [f"补充核对{'、'.join(missing[:3])}，避免只依赖单一题材或短期价格表现。"]

    hints = stock_context.get("behavior_observation_hints")
    if isinstance(hints, list) and hints:
        return [str(item).strip() for item in hints if str(item).strip()][:3]
    if stock_context:
        return []
    return ["公开股票上下文不足，需补充行情、公告、新闻或研报背景。"]


def _safe_llm_training_list(value: Any, report: dict[str, Any], limit: int = 6) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [item for item in value if isinstance(item, str)]
    else:
        candidates = []
    items = [
        item.strip()
        for item in candidates
        if item.strip() and _safe_llm_training_text(item, report) and _not_direct_investment_advice(item)
    ]
    return _unique(items)[:limit]


def _normalize_training_task(task: str) -> str:
    normalized = task.strip()
    normalized = normalized.replace("止损计划", "风险边界")
    normalized = normalized.replace("最大可接受亏损", "风险边界")
    if "当前情绪状态" in normalized or "情绪状态" in normalized:
        return ""
    if ("补全" in normalized or "缺少" in normalized) and "风险边界" in normalized:
        return ""
    if not _not_direct_investment_advice(normalized):
        return ""
    return normalized


def _unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _safe_llm_training_text(value: str, report: dict[str, Any]) -> bool:
    text = value.strip()
    stale_missing_patterns = (
        "缺少止损计划",
        "补全止损计划",
        "缺少最大可接受亏损",
        "补全最大可接受亏损",
        "缺少当前情绪状态",
        "补全当前情绪状态",
    )
    if any(pattern in text for pattern in stale_missing_patterns):
        return False
    if report.get("rule_status") == "passed" and any(word in text for word in ("不满足", "未满足", "不能通过")):
        return False
    if not _not_direct_investment_advice(text):
        return False
    return True


def _not_direct_investment_advice(value: str) -> bool:
    return not any(re.search(pattern, value) for pattern in DIRECT_ADVICE_PATTERNS)

from __future__ import annotations

from typing import Any

from .compliance import sanitize_report
from .engines import assessment_engine, normalize_training_scenario, review_engine
from .llm_assist import (
    generate_assessment_conclusion,
    generate_review_conclusion,
    llm_error_payload,
    merge_llm_fields,
)
from .memory import MemoryStore
from .models import ToolTrace, new_id, normalize_entry, utc_now
from .training_agent import run_training_check


class Orchestrator:
    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = payload.get("user_id") or "demo_user"
        message = payload.get("message") or ""
        entry = normalize_entry(payload.get("entry"), message)
        if entry == "demo":
            entry = "training"
            payload.setdefault(
                "form_data",
                {
                    "stock": "演示股票",
                    "position": 30,
                    "reason": "最近三天涨得很强",
                    "holding_period": "短线",
                    "emotion": "担心踏空",
                },
            )
            message = message or "我今天买入了某股票，仓位30%，理由是最近三天涨得很强，现在想知道能不能加仓。"

        if entry == "training":
            return run_training_check(self.store, {**payload, "entry": "training", "message": message})

        trace: list[ToolTrace] = []
        intent = self._classify_intent(entry, message, payload)
        trace.append(ToolTrace("classify_intent", "success", output_summary={"intent": intent, "entry": entry}))

        profile = self.store.get_profile(user_id)
        trace.append(
            ToolTrace(
                "user_profile_get",
                "success",
                input_summary={"user_id": user_id},
                output_summary={"trader_type": profile.trader_type, "total_score": profile.total_score},
            )
        )

        memory_query = self._memory_query_text(payload, message)
        memories = self.store.query_memories(user_id, memory_query, limit=5)
        trace.append(
            ToolTrace(
                "session_memory_query",
                "success",
                input_summary={"query": memory_query, "limit": 5},
                output_summary={"count": len(memories)},
            )
        )

        report, updated_profile = self._run_engine(entry, user_id, payload, message, profile, memories, trace)
        clean_report, compliance = sanitize_report(report)
        trace.append(
            ToolTrace(
                "compliance_guard_check",
                "success" if compliance["passed"] else "rewritten",
                output_summary={"passed": compliance["passed"], "flags": compliance["flagged_patterns"]},
            )
        )
        self.store.add_record(
            "compliance_logs",
            {
                "compliance_id": new_id("compliance"),
                "user_id": user_id,
                "entry": entry,
                "passed": compliance["passed"],
                "flags": compliance["flagged_patterns"],
                "created_at": utc_now(),
            },
        )

        if updated_profile:
            self.store.update_profile(updated_profile)
            trace.append(
                ToolTrace(
                    "user_profile_update",
                    "success",
                    output_summary={"total_score": updated_profile.total_score, "risk_level": updated_profile.risk_level},
                )
            )

        memory = self.store.write_memory(
            user_id=user_id,
            session_type=entry,
            summary=clean_report.get("summary", ""),
            decision_pattern=self._decision_pattern(clean_report),
            tags=clean_report.get("risk_tags") or clean_report.get("mistake_types") or clean_report.get("weaknesses") or [],
            report_id=clean_report.get("report_id"),
        )
        trace.append(
            ToolTrace(
                "session_memory_write",
                "success",
                output_summary={"memory_id": memory["memory_id"], "tags": memory["tags"]},
            )
        )

        self.store.add_record(
            "tool_call_logs",
            {
                "log_id": new_id("trace"),
                "user_id": user_id,
                "entry": entry,
                "intent": intent,
                "tool_trace": [item.to_dict() for item in trace],
                "created_at": utc_now(),
            },
        )

        return {
            "entry": entry,
            "intent": intent,
            "tool_trace": [item.to_dict() for item in trace],
            "report": clean_report,
            "memory_written": True,
            "memory": memory,
        }

    def _run_engine(
        self,
        entry: str,
        user_id: str,
        payload: dict[str, Any],
        message: str,
        profile,
        memories: list[dict[str, Any]],
        trace: list[ToolTrace],
    ):
        if entry == "assessment":
            report, updated_profile = assessment_engine(
                user_id=user_id,
                answers=payload.get("answers") or payload.get("form_data", {}).get("answers", []),
                trade_records=payload.get("trade_records") or [],
                session_memories=memories,
            )
            if payload.get("use_llm", True) is not False:
                try:
                    llm_report = generate_assessment_conclusion(
                        {
                            "answers": payload.get("answers") or payload.get("form_data", {}).get("answers", []),
                            "trade_records": payload.get("trade_records") or [],
                            "session_memories": memories,
                        },
                        report,
                    )
                    report = merge_llm_fields(
                        report,
                        llm_report,
                        {"total_score", "trader_type", "dimension_scores", "weaknesses", "risk_tags", "next_training_focus", "summary"},
                    )
                    updated_profile = assessment_engine(
                        user_id=user_id,
                        answers=[report.get("summary", "")],
                        trade_records=[],
                        session_memories=[],
                    )[1]
                    updated_profile.total_score = int(report.get("total_score", updated_profile.total_score))
                    updated_profile.trader_type = str(report.get("trader_type", updated_profile.trader_type))
                    if isinstance(report.get("dimension_scores"), dict):
                        updated_profile.dimension_scores = report["dimension_scores"]
                    if isinstance(report.get("risk_tags"), list):
                        updated_profile.risk_tags = report["risk_tags"]
                    if isinstance(report.get("weaknesses"), list):
                        updated_profile.weaknesses = report["weaknesses"]
                    trace.append(ToolTrace("assessment_llm_conclusion", "success"))
                except Exception as exc:
                    report.update(llm_error_payload(exc))
                    trace.append(ToolTrace("assessment_llm_conclusion", "fallback", detail=report.get("llm_error", "")))
            self.store.add_record("assessment_results", {"user_id": user_id, **report})
            trace.append(ToolTrace("assessment_engine", "success", output_summary={"score": report["total_score"]}))
            return report, updated_profile

        if entry == "review":
            trade_record = self._extract_trade_record(payload)
            report = review_engine(
                profile=profile,
                trade_record=trade_record,
                self_reflection=payload.get("self_reflection") or message,
                historical_memory=memories,
            )
            report["trade_document"] = trade_record
            if payload.get("use_llm", True) is not False:
                try:
                    llm_report = generate_review_conclusion(
                        {
                            "trade_record": trade_record,
                            "self_reflection": payload.get("self_reflection") or message,
                        },
                        report,
                    )
                    report = merge_llm_fields(
                        report,
                        llm_report,
                        {"root_cause", "mistake_types", "repeated_patterns", "new_rules", "summary"},
                    )
                    report["trade_document"] = trade_record
                    trace.append(ToolTrace("review_llm_conclusion", "success"))
                except Exception as exc:
                    report.update(llm_error_payload(exc))
                    trace.append(ToolTrace("review_llm_conclusion", "fallback", detail=report.get("llm_error", "")))
            self.store.add_record("review_reports", {"user_id": user_id, **report})
            if trade_record:
                self.store.add_record(
                    "trade_records",
                    {"trade_id": new_id("trade"), "user_id": user_id, **trade_record, "created_at": utc_now()},
                )
            trace.append(ToolTrace("review_engine", "success", output_summary={"score": report["review_score"]}))
            return report, None

        raise ValueError(f"Unsupported entry: {entry}")

    def _classify_intent(self, entry: str, message: str, payload: dict[str, Any]) -> str:
        if entry == "assessment":
            return "ability_assessment"
        if entry == "review":
            return "trade_review"
        scenario = normalize_training_scenario(payload.get("scenario") or payload.get("form_data", {}).get("scenario"), message)
        if scenario == "add":
            return "add_position_training"
        if scenario == "reduce":
            return "reduce_position_training"
        if scenario == "loss":
            return "loss_averaging_training"
        if scenario == "chase":
            return "chase_training"
        if scenario == "buy":
            return "pre_trade_training"
        if scenario == "hold":
            return "hold_position_training"
        return "behavior_training"

    def _memory_query_text(self, payload: dict[str, Any], message: str) -> str:
        form = payload.get("form_data") or payload.get("trade_plan") or payload.get("trade_record") or payload.get("trade_table") or {}
        if isinstance(form, dict):
            form_text = " ".join(str(value) for value in form.values())
        elif isinstance(form, list):
            form_text = " ".join(str(value) for value in form)
        else:
            form_text = str(form)
        return " ".join([message, form_text]).strip()

    def _extract_trade_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = payload.get("trade_record") or payload.get("form_data")
        if isinstance(record, dict):
            return record

        table = payload.get("trade_table")
        if not isinstance(table, list):
            return {}

        aliases = {
            "股票": "stock",
            "股票名称/代码": "stock",
            "买入时间": "buy_time",
            "卖出时间": "sell_time",
            "买入价格": "buy_price",
            "卖出价格": "sell_price",
            "仓位比例": "position",
            "买入理由": "buy_reason",
            "卖出理由": "sell_reason",
            "原计划是否执行": "followed_plan",
            "是否设置止损": "had_stop_loss",
            "是否临时改变计划": "changed_plan",
            "当时情绪状态": "emotion",
            "本次交易结果": "result",
            "用户自我总结": "self_summary",
        }
        out: dict[str, Any] = {}
        for row in table:
            if not isinstance(row, dict):
                continue
            key = row.get("field") or row.get("key") or row.get("label") or row.get("name")
            value = row.get("value") if "value" in row else row.get("answer")
            if not key:
                continue
            normalized_key = aliases.get(str(key), str(key))
            out[normalized_key] = value
        return out

    def _decision_pattern(self, report: dict[str, Any]) -> str:
        tags = report.get("risk_tags") or report.get("mistake_types") or report.get("weaknesses") or []
        if tags:
            return "、".join(tags)
        return report.get("trader_type") or report.get("training_decision") or "结构化训练记录"

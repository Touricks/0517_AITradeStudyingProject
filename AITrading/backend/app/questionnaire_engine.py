from __future__ import annotations

import json
from typing import Any

from .compliance import sanitize_report
from .engines import assessment_engine
from .llm_client import LLMError, OpenAICompatibleClient
from .memory import MemoryStore
from .models import ToolTrace, UserProfile, new_id, utc_now
from .questionnaire_store import get_questionnaire


DIMENSION_KEYS = [
    "market_understanding",
    "analysis_framework",
    "risk_control",
    "execution_discipline",
    "review_ability",
]


class QuestionnaireAnswerValidationError(ValueError):
    """Raised when submitted answers do not match the questionnaire contract."""


def run_questionnaire_assessment(
    store: MemoryStore,
    user_id: str,
    questionnaire_id: str,
    answers: list[dict[str, Any]],
    use_llm: bool = True,
) -> dict[str, Any]:
    trace: list[ToolTrace] = []
    questionnaire = get_questionnaire(questionnaire_id)
    trace.append(
        ToolTrace(
            "questionnaire_load",
            "success",
            output_summary={"questionnaire_id": questionnaire_id, "question_count": len(questionnaire["questions"])},
        )
    )
    answers = _normalize_answers(questionnaire, answers)
    trace.append(
        ToolTrace(
            "answer_validate",
            "success",
            output_summary={"answer_count": len(answers), "empty_count": sum(1 for item in answers if not item["answer"])},
        )
    )

    llm_error = ""
    raw_report: dict[str, Any]
    if use_llm:
        try:
            raw_report = _call_kimi(questionnaire, answers)
            trace.append(ToolTrace("kimi_profile_generate", "success", output_summary={"model_source": "openai_compatible"}))
        except LLMError as exc:
            llm_error = str(exc)
            raw_report = _fallback_report(user_id, questionnaire, answers)
            trace.append(ToolTrace("kimi_profile_generate", "fallback", detail=llm_error))
    else:
        raw_report = _fallback_report(user_id, questionnaire, answers)
        trace.append(ToolTrace("kimi_profile_generate", "skipped", detail="use_llm=false"))

    report = _validate_and_normalize_report(raw_report, questionnaire_id)
    trace.append(ToolTrace("schema_validate", "success", output_summary={"total_score": report["total_score"]}))

    profile = _profile_from_report(user_id, report)
    store.update_profile(profile)
    trace.append(
        ToolTrace(
            "user_profile_update",
            "success",
            output_summary={"total_score": profile.total_score, "trader_type": profile.trader_type},
        )
    )

    clean_report, compliance = sanitize_report(report)
    trace.append(
        ToolTrace(
            "compliance_guard_check",
            "success" if compliance["passed"] else "rewritten",
            output_summary={"passed": compliance["passed"], "flags": compliance["flagged_patterns"]},
        )
    )

    result_record = store.add_record(
        "questionnaire_results",
        {
            "result_id": clean_report["report_id"],
            "user_id": user_id,
            "questionnaire_id": questionnaire_id,
            "answers": answers,
            "report": clean_report,
            "llm_error": llm_error,
            "created_at": utc_now(),
        },
    )
    store.add_record("assessment_results", {"user_id": user_id, **clean_report})
    memory = store.write_memory(
        user_id=user_id,
        session_type="questionnaire_assessment",
        summary=clean_report.get("profile_summary") or clean_report.get("summary", ""),
        decision_pattern="、".join(clean_report.get("risk_tags", []) or clean_report.get("weaknesses", [])),
        tags=clean_report.get("risk_tags", []) or clean_report.get("weaknesses", []),
        report_id=clean_report["report_id"],
    )
    trace.append(
        ToolTrace(
            "session_memory_write",
            "success",
            output_summary={"memory_id": memory["memory_id"], "result_id": result_record["result_id"]},
        )
    )
    store.add_record(
        "tool_call_logs",
        {
            "log_id": new_id("trace"),
            "user_id": user_id,
            "entry": "questionnaire_assessment",
            "intent": "ability_assessment",
            "tool_trace": [item.to_dict() for item in trace],
            "created_at": utc_now(),
        },
    )

    return {
        "entry": "assessment",
        "intent": "questionnaire_assessment",
        "questionnaire": {
            "id": questionnaire["id"],
            "title": questionnaire["title"],
        },
        "tool_trace": [item.to_dict() for item in trace],
        "report": clean_report,
        "memory_written": True,
        "memory": memory,
    }


def _call_kimi(questionnaire: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    client = OpenAICompatibleClient()
    messages = [
        {
            "role": "system",
            "content": (
                "你是交易能力训练系统的问卷评估引擎。只输出 JSON 对象，不要 Markdown。"
                "本系统仅用于投资教育和交易能力训练，不提供个股推荐、买卖点或收益承诺。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "根据问卷题目、评分规则和用户答案生成固定格式用户画像。",
                    "questionnaire": questionnaire,
                    "answers": answers,
                    "required_schema": _schema_description(),
                },
                ensure_ascii=False,
            ),
        },
    ]
    return client.chat_json(messages)


def _normalize_answers(questionnaire: dict[str, Any], answers: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(answers, list):
        raise QuestionnaireAnswerValidationError("answers must be a JSON array")

    questions = questionnaire.get("questions", [])
    expected_ids = [str(item.get("id", "")) for item in questions]
    question_by_id = {str(item.get("id", "")): item for item in questions}
    submitted: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []

    for item in answers:
        if not isinstance(item, dict):
            raise QuestionnaireAnswerValidationError("each answer must be a JSON object")
        question_id = str(item.get("question_id", "")).strip()
        if not question_id:
            raise QuestionnaireAnswerValidationError("each answer must include question_id")
        if question_id in submitted:
            duplicates.append(question_id)
        submitted[question_id] = item

    submitted_ids = set(submitted)
    expected_set = set(expected_ids)
    missing = [question_id for question_id in expected_ids if question_id not in submitted_ids]
    unknown = sorted(submitted_ids - expected_set)
    if missing or unknown or duplicates:
        detail = {
            "missing_question_ids": missing,
            "unknown_question_ids": unknown,
            "duplicate_question_ids": sorted(set(duplicates)),
            "expected_question_ids": expected_ids,
        }
        raise QuestionnaireAnswerValidationError(json.dumps(detail, ensure_ascii=False))

    normalized = []
    for question_id in expected_ids:
        raw = submitted[question_id]
        answer = raw.get("answer", "")
        normalized.append(
            {
                "question_id": question_id,
                "question_text": str(question_by_id[question_id].get("text", "")),
                "answer": "" if answer is None else str(answer),
            }
        )
    return normalized


def _fallback_report(user_id: str, questionnaire: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    answer_text = [
        f"{item.get('question_id', '')}: {item.get('answer', '')}"
        for item in answers
    ]
    report, _profile = assessment_engine(user_id, answer_text, [], [])
    return {
        "questionnaire_id": questionnaire["id"],
        "total_score": report["total_score"],
        "dimension_scores": report["dimension_scores"],
        "trader_type": report["trader_type"],
        "risk_level": _profile.risk_level,
        "weaknesses": report["weaknesses"],
        "risk_tags": report["risk_tags"],
        "profile_summary": report["summary"],
        "evidence": [],
        "next_training_focus": report["next_training_focus"],
        "recommended_tasks": [f"围绕{item}完成一次训练记录" for item in report["next_training_focus"]],
    }


def _validate_and_normalize_report(raw: dict[str, Any], questionnaire_id: str) -> dict[str, Any]:
    report = dict(raw)
    report["questionnaire_id"] = str(report.get("questionnaire_id") or questionnaire_id)
    report["report_id"] = str(report.get("report_id") or new_id("questionnaire"))
    report["total_score"] = _clamp_int(report.get("total_score"), 0, 100)
    scores = report.get("dimension_scores") if isinstance(report.get("dimension_scores"), dict) else {}
    report["dimension_scores"] = {
        key: _clamp_int(scores.get(key), 0, 20)
        for key in DIMENSION_KEYS
    }
    if sum(report["dimension_scores"].values()) and abs(sum(report["dimension_scores"].values()) - report["total_score"]) > 25:
        report["total_score"] = sum(report["dimension_scores"].values())
    report["trader_type"] = str(report.get("trader_type") or _trader_type(report["total_score"]))
    report["risk_level"] = str(report.get("risk_level") or _risk_level(report["total_score"]))
    for key in ("weaknesses", "risk_tags", "next_training_focus", "recommended_tasks"):
        value = report.get(key)
        report[key] = [str(item) for item in value] if isinstance(value, list) else []
    evidence = report.get("evidence")
    report["evidence"] = evidence if isinstance(evidence, list) else []
    report["profile_summary"] = str(report.get("profile_summary") or report.get("summary") or "")
    report["summary"] = report["profile_summary"]
    report["schema_version"] = "questionnaire_profile.v1"
    report["created_at"] = str(report.get("created_at") or utc_now())
    return report


def _profile_from_report(user_id: str, report: dict[str, Any]) -> UserProfile:
    return UserProfile(
        user_id=user_id,
        trader_type=report["trader_type"],
        total_score=report["total_score"],
        dimension_scores=report["dimension_scores"],
        risk_tags=report["risk_tags"],
        weaknesses=report["weaknesses"],
        training_stage="foundation" if report["total_score"] < 70 else "advanced",
        risk_level=report["risk_level"],
    )


def _schema_description() -> dict[str, Any]:
    return {
        "questionnaire_id": "string",
        "total_score": "integer 0-100",
        "dimension_scores": {key: "integer 0-20" for key in DIMENSION_KEYS},
        "trader_type": "新手型|经验型散户|规则型交易者|成熟交易者|专业型交易者",
        "risk_level": "low|medium|medium_high|high",
        "weaknesses": ["string"],
        "risk_tags": ["string"],
        "profile_summary": "string",
        "evidence": [{"question_id": "string", "finding": "string"}],
        "next_training_focus": ["string"],
        "recommended_tasks": ["string"],
    }


def _clamp_int(value: Any, low: int, high: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _trader_type(score: int) -> str:
    if score <= 30:
        return "新手型"
    if score <= 50:
        return "经验型散户"
    if score <= 70:
        return "规则型交易者"
    if score <= 85:
        return "成熟交易者"
    return "专业型交易者"


def _risk_level(score: int) -> str:
    if score <= 40:
        return "high"
    if score <= 60:
        return "medium_high"
    if score <= 80:
        return "medium"
    return "low"

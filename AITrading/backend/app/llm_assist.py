from __future__ import annotations

import json
from typing import Any

from .llm_client import LLMError, OpenAICompatibleClient


def generate_assessment_conclusion(payload: dict[str, Any], heuristic_report: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是交易能力画像评估引擎。只输出 JSON 对象，不要 Markdown。"
                "只能评估交易能力、行为模式和训练方向，不能提供个股推荐、买卖点或收益承诺。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "根据用户评估答案、交易记录和历史记忆，生成能力画像结论。不要判断任何具体标的是否值得买卖。",
                    "user_payload": payload,
                    "heuristic_report": heuristic_report,
                    "required_schema": {
                        "total_score": "integer 0-100",
                        "trader_type": "string",
                        "dimension_scores": {
                            "market_understanding": "integer 0-20",
                            "analysis_framework": "integer 0-20",
                            "risk_control": "integer 0-20",
                            "execution_discipline": "integer 0-20",
                            "review_ability": "integer 0-20",
                        },
                        "weaknesses": ["string"],
                        "risk_tags": ["string"],
                        "next_training_focus": ["string"],
                        "summary": "string",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    return OpenAICompatibleClient().chat_json(messages, schema_name="assessment_conclusion")


def generate_training_conclusion(payload: dict[str, Any], heuristic_report: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是交易行为训练与买入前决策支持引擎。只输出 JSON 对象，不要 Markdown。"
                "只能基于后端评分结果解释交易计划完整度、行为风险、需要补充的公开资料和训练任务。"
                "不能提供买入、卖出、加仓、减仓建议，不能提供买卖点、目标价或收益承诺。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": (
                        "根据用户交易意图、交易计划、stock_context 和 heuristic_report，生成买入前决策支持建议。"
                        "stock_context 只能用于识别用户行为逻辑与公开背景是否一致，以及提示还缺哪些公开资料，"
                        "不要判断个股是否值得买卖。plan_score、rule_status、missing_fields、risk_tags "
                        "完全以 heuristic_report 为准，不要重算、不要覆盖、不要扩展。"
                        "当前必填字段只有 stock、reason、risk_boundary，不要要求止损计划、最大可接受亏损或当前情绪状态。"
                        "输出必须是训练与检查建议，例如资料核对、风险提醒、计划改进任务和暂停条件；"
                        "不要出现“建议买入/卖出/加仓/减仓”“可以买/可以卖”“目标价”等直接投资建议。"
                    ),
                    "user_payload": payload,
                    "heuristic_report": heuristic_report,
                    "required_schema": {
                        "training_decision": "string，必须服从 heuristic_report.rule_status",
                        "training_tasks": ["string，训练任务，不含直接买卖指令"],
                        "summary": "string，解释评分结果和主要行为风险",
                        "decision_support_advice": ["string，买入前检查建议，不含直接买卖结论"],
                        "risk_warnings": ["string，基于 risk_tags 和 stock_context 的风险提醒"],
                        "missing_research_items": ["string，还需要补充核对的公开资料"],
                        "plan_improvement_tasks": ["string，交易计划需要补强的任务"],
                        "pause_conditions": ["string，触发后应暂停本次计划的条件"],
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    return OpenAICompatibleClient().chat_json(messages, schema_name="training_conclusion")


def generate_review_conclusion(trade_document: dict[str, Any], heuristic_report: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是交易复盘审阅引擎。只输出 JSON 对象，不要 Markdown。"
                "只能做交易过程复盘、错误归因和训练规则生成，不能提供个股推荐、买卖点或收益承诺。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "根据交易表格转换后的 JSON 文档，审阅用户交易过程并输出复盘结论。",
                    "trade_document": trade_document,
                    "heuristic_report": heuristic_report,
                    "required_schema": {
                        "root_cause": "string",
                        "mistake_types": ["string"],
                        "repeated_patterns": ["string"],
                        "new_rules": ["string"],
                        "summary": "string",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    return OpenAICompatibleClient().chat_json(messages, schema_name="review_conclusion")


def merge_llm_fields(report: dict[str, Any], llm_report: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any]:
    merged = dict(report)
    for key in allowed_keys:
        if key in llm_report:
            merged[key] = llm_report[key]
    merged["llm_used"] = True
    return merged


def llm_error_payload(exc: Exception) -> dict[str, Any]:
    return {"llm_used": False, "llm_error": str(exc) if isinstance(exc, LLMError) else f"{type(exc).__name__}: {exc}"}

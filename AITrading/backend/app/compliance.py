from __future__ import annotations

import re
from typing import Any

from .models import COMPLIANCE_NOTICE


FORBIDDEN_PATTERNS = [
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
    r"跌破.+卖出",
    r"目标价",
    r"稳赚",
    r"必涨",
    r"一定上涨",
    r"买卖信号",
]


REPLACEMENTS = [
    (re.compile(r"建议你?买入"), "系统不判断个股是否可买，只评估交易计划完整度"),
    (re.compile(r"建议你?卖出"), "当前计划缺少退出条件，请补全"),
    (re.compile(r"建议你?加仓"), "系统不判断是否应增加仓位，只评估计划约束"),
    (re.compile(r"建议你?减仓"), "系统不判断是否应降低仓位，只评估退出规则"),
    (re.compile(r"可以买"), "当前行为需先满足训练规则"),
    (re.compile(r"可以卖"), "当前计划需补全退出条件"),
    (re.compile(r"可以加仓"), "当前行为需先满足训练规则"),
    (re.compile(r"可以减仓"), "当前计划需补全退出条件"),
    (re.compile(r"跌破(.+?)卖出"), "请根据最大可承受亏损设定退出条件"),
    (re.compile(r"目标价"), "目标区域"),
    (re.compile(r"稳赚|必涨|一定上涨"), "存在不确定性"),
]


def check_text(text: str) -> dict[str, Any]:
    flagged = []
    rewritten = text
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, rewritten):
            flagged.append(pattern)
    for pattern, replacement in REPLACEMENTS:
        rewritten = pattern.sub(replacement, rewritten)
    if COMPLIANCE_NOTICE not in rewritten:
        rewritten = f"{rewritten}\n\n合规提示：{COMPLIANCE_NOTICE}"
    return {
        "passed": not flagged,
        "flagged_patterns": flagged,
        "text": rewritten,
        "notice": COMPLIANCE_NOTICE,
    }


def sanitize_report(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    clean = dict(report)
    text_parts = []
    for key, value in report.items():
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            text_parts.extend(str(item) for item in value)
    compliance = check_text("\n".join(text_parts))
    clean["compliance_notice"] = COMPLIANCE_NOTICE
    clean["compliance_passed"] = compliance["passed"]
    clean["compliance_flags"] = compliance["flagged_patterns"]
    return clean, compliance

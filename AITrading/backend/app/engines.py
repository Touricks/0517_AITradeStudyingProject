from __future__ import annotations

from statistics import mean
from typing import Any

from .models import UserProfile, clamp, new_id, utc_now


DIMENSIONS = {
    "market_understanding": "市场理解",
    "analysis_framework": "分析框架",
    "risk_control": "风险控制",
    "execution_discipline": "执行纪律",
    "review_ability": "复盘能力",
}

POSITIVE_SIGNALS = {
    "market_understanding": ["不确定", "概率", "周期", "市场环境", "策略失效"],
    "analysis_framework": ["框架", "依据", "基本面", "技术面", "规则", "验证"],
    "risk_control": ["止损", "最大亏损", "风险", "盈亏比", "回撤"],
    "execution_discipline": ["计划", "执行", "不临时", "纪律", "不交易"],
    "review_ability": ["复盘", "记录", "总结", "归因", "改进"],
}

NEGATIVE_SIGNALS = ["凭感觉", "满仓", "追涨", "补仓", "赚回来", "必涨", "消息", "冲动", "没有止损"]
RISK_TAGS = {"追涨", "止损缺失", "仓位偏高", "补仓冲动", "报复性交易", "计划缺失", "消息驱动"}


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def trader_type(score: int) -> str:
    if score <= 30:
        return "新手型"
    if score <= 50:
        return "经验型散户"
    if score <= 70:
        return "规则型交易者"
    if score <= 85:
        return "成熟交易者"
    return "专业型交易者"


def risk_level(score: int, tags: list[str]) -> str:
    if score < 45 or len(tags) >= 4:
        return "high"
    if score < 65 or len(tags) >= 2:
        return "medium_high"
    return "medium"


def assessment_engine(
    user_id: str,
    answers: list[Any],
    trade_records: list[dict[str, Any]],
    session_memories: list[dict[str, Any]],
) -> tuple[dict[str, Any], UserProfile]:
    text = _flatten_text(answers) + " " + _flatten_text(trade_records) + " " + _flatten_text(session_memories)
    scores: dict[str, int] = {}
    for dimension, keywords in POSITIVE_SIGNALS.items():
        score = 8
        score += sum(2 for keyword in keywords if keyword in text)
        score -= sum(1 for keyword in NEGATIVE_SIGNALS if keyword in text)
        scores[dimension] = clamp(score)

    total = sum(scores.values())
    weaknesses = [DIMENSIONS[key] for key, score in scores.items() if score < 11]
    risk_tags = extract_risk_tags(text)
    profile = UserProfile(
        user_id=user_id,
        trader_type=trader_type(total),
        total_score=total,
        dimension_scores=scores,
        risk_tags=risk_tags,
        weaknesses=weaknesses,
        training_stage="foundation" if total < 70 else "advanced",
        risk_level=risk_level(total, risk_tags),
    )
    report = {
        "report_id": new_id("assessment"),
        "total_score": total,
        "trader_type": profile.trader_type,
        "dimension_scores": scores,
        "weaknesses": weaknesses,
        "risk_tags": risk_tags,
        "next_training_focus": next_training_focus(weaknesses, risk_tags),
        "summary": f"当前画像为{profile.trader_type}，主要训练重点是{','.join(next_training_focus(weaknesses, risk_tags)) or '保持交易记录'}。",
        "created_at": utc_now(),
    }
    return report, profile


def extract_risk_tags(text: str) -> list[str]:
    rules = [
        ("追涨", ["追涨", "涨得很强", "连续上涨", "FOMO", "踏空"]),
        ("止损缺失", ["没有止损", "未设置止损", "无止损", "止损为空"]),
        ("仓位偏高", ["满仓", "70%仓位", "仓位70", "仓位 70", "仓位80", "仓位 80"]),
        ("补仓冲动", ["补仓", "摊低成本"]),
        ("报复性交易", ["赚回来", "立刻回本", "报复"]),
        ("计划缺失", ["没计划", "没有计划", "临时", "随便"]),
        ("消息驱动", ["小道消息", "听消息", "看到消息", "别人推荐", "群里", "别人赚钱"]),
    ]
    tags = []
    for tag, keywords in rules:
        if any(_contains_unnegated_keyword(text, keyword) for keyword in keywords):
            tags.append(tag)
    return tags


def _contains_unnegated_keyword(text: str, keyword: str) -> bool:
    start = 0
    while True:
        index = text.find(keyword, start)
        if index < 0:
            return False
        prefix = text[max(0, index - 8):index]
        if not any(marker in prefix for marker in ("不", "不会", "不要", "不能", "禁止", "避免", "拒绝")):
            return True
        start = index + len(keyword)


def next_training_focus(weaknesses: list[str], risk_tags: list[str]) -> list[str]:
    focus = []
    if "风险控制" in weaknesses or "止损缺失" in risk_tags:
        focus.append("交易前止损与最大亏损训练")
    if "执行纪律" in weaknesses or "追涨" in risk_tags:
        focus.append("冲动交易拦截训练")
    if "复盘能力" in weaknesses:
        focus.append("复盘记录训练")
    if "仓位偏高" in risk_tags:
        focus.append("仓位预算训练")
    return focus[:4]


REQUIRED_TRAINING_FIELDS = {
    "stock": {
        "label": "股票名称/代码",
        "aliases": ("stock", "symbol", "股票", "股票名称/代码"),
    },
    "reason": {
        "label": "买入理由",
        "aliases": ("reason", "buy_reason", "买入理由", "本次交易理由"),
    },
    "risk_boundary": {
        "label": "风险边界",
        "aliases": (
            "risk_boundary",
            "risk_plan",
            "风险边界",
            "如果判断错了怎么办",
            "止损计划",
            "stop_loss",
            "最大可接受亏损",
            "max_loss",
            "失效条件",
            "invalid_condition",
        ),
    },
}

OPTIONAL_TRAINING_FIELDS = {
    "position": ("position", "planned_position", "current_position", "当前仓位", "计划买入仓位"),
    "holding_period": ("holding_period", "预期持有周期"),
}

TRAINING_SCENARIOS = {
    "buy": "我准备买入",
    "hold": "我已经持仓",
    "add": "我想加仓",
    "reduce": "我想减仓",
    "loss": "我亏损后想补仓",
    "chase": "我看到上涨想追",
    "check": "我想检查交易计划",
}

SCENARIO_ALIASES = {
    "pre_trade": "buy",
    "buy": "buy",
    "hold": "hold",
    "add": "add",
    "add_position": "add",
    "reduce": "reduce",
    "reduce_position": "reduce",
    "loss": "loss",
    "loss_averaging": "loss",
    "chase": "chase",
    "check": "check",
    "plan_check": "check",
}


def normalize_training_scenario(raw: Any, message: str = "") -> str:
    value = str(raw or "").strip()
    if value in SCENARIO_ALIASES:
        return SCENARIO_ALIASES[value]
    text = f"{value} {message}"
    if "补仓" in text or "亏损" in text:
        return "loss"
    if "加仓" in text:
        return "add"
    if "减仓" in text:
        return "reduce"
    if "追" in text or "踏空" in text:
        return "chase"
    if "持仓" in text:
        return "hold"
    if "买入" in text:
        return "buy"
    return "check"


def training_engine(
    profile: UserProfile,
    trade_plan: dict[str, Any],
    message: str,
    memory_patterns: list[dict[str, Any]],
    research_context: list[dict[str, Any]],
    scenario: str = "check",
) -> dict[str, Any]:
    text = message + " " + _flatten_text(trade_plan)
    missing = []
    completed = 0
    for field in REQUIRED_TRAINING_FIELDS.values():
        value = _first_present(trade_plan, field["aliases"])
        if value:
            completed += 1
        else:
            missing.append(field["label"])

    memory_risk_tags = [
        tag
        for item in memory_patterns
        for tag in item.get("tags", [])
        if tag in RISK_TAGS
    ]
    risk_tags = sorted(set(extract_risk_tags(text) + memory_risk_tags))
    if "风险边界" in missing and "止损缺失" not in risk_tags:
        risk_tags.append("止损缺失")
    if len(missing) >= 3 and "计划缺失" not in risk_tags:
        risk_tags.append("计划缺失")
    position = _as_number(_first_present(trade_plan, OPTIONAL_TRAINING_FIELDS["position"]))
    if position and position >= 60 and "仓位偏高" not in risk_tags:
        risk_tags.append("仓位偏高")

    optional_completed = sum(
        1
        for aliases in OPTIONAL_TRAINING_FIELDS.values()
        if _first_present(trade_plan, aliases)
    )
    plan_score = int((completed / len(REQUIRED_TRAINING_FIELDS)) * 75)
    plan_score += optional_completed * 5
    plan_score += 10 if research_context else 0
    plan_score -= min(30, len(risk_tags) * 6)
    plan_score = max(0, min(100, plan_score))

    critical = {"止损缺失", "追涨", "补仓冲动", "报复性交易"} & set(risk_tags)
    rule_status = "passed" if plan_score >= 75 and not critical else "not_passed"
    tasks = build_training_tasks(missing, risk_tags, profile)
    decision = "满足本次训练规则" if rule_status == "passed" else "当前不满足本次训练规则"
    return {
        "report_id": new_id("training"),
        "scenario": scenario,
        "scenario_label": TRAINING_SCENARIOS.get(scenario, "我想检查交易计划"),
        "plan_score": plan_score,
        "rule_status": rule_status,
        "training_decision": decision,
        "risk_tags": risk_tags,
        "missing_fields": missing,
        "training_tasks": tasks,
        "research_context_used": len(research_context),
        "next_requirement": "下一次训练需先写清股票名称/代码、买入理由与风险边界。",
        "summary": f"{decision}，计划完整度 {plan_score}/100，主要风险标签：{','.join(risk_tags) or '暂无'}。",
        "created_at": utc_now(),
    }


def build_training_tasks(missing: list[str], risk_tags: list[str], profile: UserProfile) -> list[str]:
    tasks = [f"补全{field}" for field in missing]
    if "止损缺失" in risk_tags:
        tasks.append("写明判断错误时的处理方式、最大可接受亏损或逻辑失效条件")
    if "追涨" in risk_tags:
        tasks.append("写出本次交易不是短期情绪驱动的证据")
    if "仓位偏高" in risk_tags:
        tasks.append("根据当前能力等级重新核对仓位预算")
    if "补仓冲动" in risk_tags:
        tasks.append("区分加仓条件与亏损补仓冲动")
    if profile.risk_level in {"high", "medium_high"}:
        tasks.append("未来3笔交易必须先完成交易计划表")
    return list(dict.fromkeys(tasks))[:6]


def _first_present(payload: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        value = payload.get(alias)
        if value not in (None, ""):
            return value
    return None


def review_engine(
    profile: UserProfile,
    trade_record: dict[str, Any],
    self_reflection: str,
    historical_memory: list[dict[str, Any]],
) -> dict[str, Any]:
    text = _flatten_text(trade_record) + " " + self_reflection
    dimensions = {
        "plan_integrity": 20 if trade_record.get("buy_reason") and trade_record.get("stop_loss_plan") else 10,
        "execution_consistency": 20 if truthy(trade_record.get("followed_plan")) else 9,
        "risk_control": 20 if trade_record.get("stop_loss_plan") else 8,
        "position_management": 20 if (_as_number(trade_record.get("position")) or 0) <= 40 else 10,
        "emotion_control": 20 if not any(word in text for word in ("冲动", "害怕", "踏空", "赚回来")) else 9,
    }
    review_score = int(mean(dimensions.values()) * 5)
    mistake_types = extract_mistake_types(text, dimensions)
    memory_tags = [tag for item in historical_memory for tag in item.get("tags", [])]
    repeated = sorted(set(mistake_types) & set(memory_tags))
    root_cause = root_cause_from_mistakes(mistake_types)
    new_rules = build_review_rules(mistake_types, repeated, profile)
    return {
        "report_id": new_id("review"),
        "review_score": review_score,
        "dimension_scores": dimensions,
        "mistake_types": mistake_types,
        "root_cause": root_cause,
        "repeated_patterns": repeated,
        "new_rules": new_rules,
        "summary": f"本次复盘评分 {review_score}/100，主要问题是{root_cause}。",
        "created_at": utc_now(),
    }


def extract_mistake_types(text: str, dimensions: dict[str, int]) -> list[str]:
    mistakes = extract_risk_tags(text)
    if dimensions["plan_integrity"] < 15:
        mistakes.append("计划缺失")
    if dimensions["execution_consistency"] < 15:
        mistakes.append("止损不执行")
    if dimensions["position_management"] < 15:
        mistakes.append("仓位过重")
    if "卖飞" in text or "拿不住" in text:
        mistakes.append("盈利拿不住")
    return list(dict.fromkeys(mistakes))


def build_review_rules(mistakes: list[str], repeated: list[str], profile: UserProfile) -> list[str]:
    rules = []
    if "计划缺失" in mistakes:
        rules.append("未来3笔交易买入前必须填写入场理由、止损计划、退出条件和复盘时间。")
    if "止损不执行" in mistakes or "止损缺失" in mistakes:
        rules.append("亏损触及预设条件时先复盘计划，不在盘中临时扩大亏损边界。")
    if "追涨" in mistakes:
        rules.append("连续上涨后的交易必须写出失效条件和不交易条件。")
    if repeated:
        rules.append(f"下次训练重点检查重复模式：{','.join(repeated)}。")
    if profile.training_stage == "foundation":
        rules.append("当前阶段优先训练规则执行，不以单笔盈亏评价能力。")
    return rules[:5]


def root_cause_from_mistakes(mistakes: list[str]) -> str:
    if "止损不执行" in mistakes or "计划缺失" in mistakes:
        return "执行纪律与交易前计划不足，而非单纯信息不足"
    if "追涨" in mistakes or "报复性交易" in mistakes:
        return "情绪驱动高于规则驱动"
    if "仓位过重" in mistakes or "仓位偏高" in mistakes:
        return "仓位预算与风险承受能力不匹配"
    return "需要继续积累结构化复盘样本"


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except ValueError:
        return None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "是", "执行", "已执行"}

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


QUESTIONNAIRE_DIR = Path(__file__).resolve().parents[2] / "assets" / "questionnaires"
FULL_ASSESSMENT_ID = "full_assessment"
QUESTIONNAIRE_ORDER = [
    "trading_cognition",
    "analysis_framework",
    "risk_control",
    "position_management",
    "trade_plan",
    "emotion_discipline",
    "review_ability",
    "scenario_maturity",
]


class QuestionnaireNotFound(KeyError):
    """Raised when a questionnaire id is unknown."""


def list_questionnaires() -> list[dict[str, Any]]:
    questionnaires = [_build_full_assessment()]
    questionnaires.extend(get_questionnaire(questionnaire_id) for questionnaire_id in QUESTIONNAIRE_ORDER)
    items = []
    for questionnaire in questionnaires:
        items.append(
            {
                "id": questionnaire["id"],
                "title": questionnaire["title"],
                "description": questionnaire.get("description", ""),
                "dimensions": questionnaire.get("dimensions", []),
                "question_count": len(questionnaire.get("questions", [])),
            }
        )
    return items


def get_questionnaire(questionnaire_id: str) -> dict[str, Any]:
    if questionnaire_id == FULL_ASSESSMENT_ID:
        return _build_full_assessment()
    path = QUESTIONNAIRE_DIR / f"{questionnaire_id}.json"
    if not path.exists():
        raise QuestionnaireNotFound(questionnaire_id)
    return _load(path)


def _build_full_assessment() -> dict[str, Any]:
    sections = []
    questions = []
    dimensions = set()
    score_weight: dict[str, float] = {}
    for questionnaire_id in QUESTIONNAIRE_ORDER:
        questionnaire = _load(QUESTIONNAIRE_DIR / f"{questionnaire_id}.json")
        sections.append(
            {
                "id": questionnaire["id"],
                "title": questionnaire["title"],
                "question_ids": [question["id"] for question in questionnaire.get("questions", [])],
            }
        )
        questions.extend(questionnaire.get("questions", []))
        dimensions.update(questionnaire.get("dimensions", []))
        for dimension, weight in questionnaire.get("score_weight", {}).items():
            score_weight[dimension] = score_weight.get(dimension, 0.0) + float(weight)

    total_weight = sum(score_weight.values()) or 1.0
    normalized_weight = {
        dimension: round(weight / total_weight, 4)
        for dimension, weight in sorted(score_weight.items())
    }
    return {
        "id": FULL_ASSESSMENT_ID,
        "title": "完整交易能力画像问卷",
        "description": "合并八套分项问卷的 40 个问题，用于一次性生成完整用户画像和综合得分。",
        "dimensions": sorted(dimensions),
        "sections": sections,
        "questions": questions,
        "score_weight": normalized_weight,
    }


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("questions", [])
    data.setdefault("dimensions", [])
    return data

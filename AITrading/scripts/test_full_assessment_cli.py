#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_ANSWERS = {
    "q1": "我认为最重要的是 C，控制亏损和风险回报比。交易不是寻找必涨标的，而是在不确定性里控制单笔风险、赔率和长期样本。",
    "q2": "短期价格受情绪、资金和消息投票影响，长期会回到企业盈利、行业周期和现金流质量。我的交易会区分短线情绪和长期基本面。",
    "q3": "不能。一次交易结果只能说明这次样本的盈亏，不能证明判断正确。需要看长期策略样本、回撤、胜率赔率和执行一致性。",
    "q4": "不会因为连续盈利就放大仓位。我会复核是否符合策略边界，保持单笔最大亏损不超过账户 1%-2%，最多小幅提高到计划上限。",
    "q5": "我会先检查样本数量、是否违反交易计划、市场环境是否变化、最大回撤是否超过策略预设。如果连续亏损 3 次会暂停并复盘。",
    "q6": "我会按市场环境、行业景气度、公司基本面、估值位置、技术结构、成交量和风险回报排序。先看大环境，再看标的质量和买入位置。",
    "q7": "更偏向 B 和 A 结合：基本面筛选标的，技术面决定入场和止损。原因是我需要框架和规则，避免只靠情绪或题材热度交易。",
    "q8": "如果基本面看好但技术面持续走弱，我会降低仓位或等待，不会提前满仓。只有价格重新站回关键位且风险回报合适才考虑。",
    "q9": "我会看位置、成交量、上涨幅度、市场情绪和盈亏比。若短期涨幅过大且止损空间太远，会判断为过热，不追涨。",
    "q10": "我看指数趋势、成交量、赚钱效应、板块轮动、宏观流动性和自己的策略适配度。市场环境差时降低仓位或不交易。",
    "q11": "单笔最多亏损总资金 1%-2%。如果止损距离太大，就降低仓位；如果算出来仓位太小或赔率不足，就放弃交易。",
    "q12": "会。买入前必须设止损，依据是交易逻辑失效位置、关键支撑跌破、最大亏损额度和波动率，不临时扩大止损。",
    "q13": "如果下跌 8% 已触发预设止损，我会执行止损。若未触发但基本面没变，也会复核仓位和市场环境，不会盲目补仓。",
    "q14": "止损是承认不确定性，不是承认失败。交易要先保证活下来，亏损可控才能让长期策略有机会体现。",
    "q15": "我会先算最大亏损和止损距离，控制仓位，要求至少 2:1 以上风险回报。如果潜在亏损超过预算，即使看好也放弃。",
    "q16": "我选择 C，根据止损距离和最大亏损额度决定仓位。公式是最大可亏金额除以单股风险，再结合组合总仓位限制。",
    "q17": "账户 10 万，单笔最多亏 2% 是 2000 元；买入 100、止损 95，单股风险 5 元，所以最多 400 股。",
    "q18": "如果已有 70% 仓位，我不会直接加仓。会比较新机会和原持仓的风险回报，必要时换仓，组合总风险不能超限。",
    "q19": "会加仓，但只在盈利、趋势确认、原计划允许、加仓后整体风险仍可控时加仓。亏损中不为摊低成本而加仓。",
    "q20": "加仓通常是在交易正确后扩大优势，补仓是在亏损后摊低成本。补仓风险更高，必须有事前规则，否则不做。",
    "q21": "交易前必须明确买入理由、入场价格、止损位置、目标区域、仓位大小、持有周期、失效条件和复盘时间点。",
    "q22": "横盘 10 天后我会复核持有周期和机会成本。如果没有触发止损但逻辑迟迟不兑现，会减仓或退出，避免资金低效占用。",
    "q23": "一般不会盘中临时改计划。只有出现重大公告、流动性异常或原假设被事实证伪时才允许调整，并记录原因。",
    "q24": "止盈依据是目标价、趋势破坏、收益回撤规则和风险回报变化。盈利后会用移动止盈保护利润，不靠感觉卖出。",
    "q25": "会区分。看对方向不等于赚到钱，仓位、买点、止损、持有周期和执行纪律都会影响最终结果。",
    "q26": "最容易影响我的是踏空和连续亏损。我会用交易清单、冷静期和固定仓位规则降低情绪触发。",
    "q27": "有过 FOMO 买入，看到热门股连续上涨就追，结果止损空间过大。现在要求写明买入理由、止损和赔率，否则不下单。",
    "q28": "卖飞后我会复盘卖出是否符合计划。如果符合规则，就接受结果；如果规则有问题，再调整策略，不因为后悔去追高。",
    "q29": "我会先判断止损当时是否符合计划。如果符合，那是正确执行；如果止损位设置不合理，再改进规则，而不是责怪结果。",
    "q30": "有过亏损后想立刻赚回来的冲动。现在如果连续亏损 2-3 笔，会暂停交易至少一天，复盘后才能继续。",
    "q31": "我记录每一笔交易，包括标的、日期、入场理由、仓位、止损、目标、实际执行、情绪、盈亏和复盘结论。",
    "q32": "坏交易是过程违反计划或风险不可控；亏钱交易可能是按计划执行但结果不利。评估重点是过程质量，不只看盈亏。",
    "q33": "最近失败交易是追涨买入，买入理由偏情绪，止损执行慢。下次必须先算最大亏损，涨幅过大且赔率不足时不交易。",
    "q34": "评估策略要看足够样本、胜率赔率、最大回撤、不同市场环境表现、执行成本和失效条件，不能只看短期收益。",
    "q35": "我会降低仓位或暂停策略，检查市场环境是否改变、样本是否足够、回撤是否超过阈值。确认失效前不扩大仓位。",
    "s1": "不会直接买。先判断是否过热、是否有合理止损和赔率。若止损距离太远或只是情绪热度驱动，就放弃。",
    "s2": "如果买入理由仍成立但跌破预设止损，我会先止损或减仓，不会盲目加仓。跌到 40 元必须重新评估逻辑是否失效。",
    "s3": "我会按移动止盈处理，保护部分利润。如果趋势未破坏可继续持有，但会设定回撤线，避免盈利变亏损。",
    "s4": "看不懂公告时先控制风险，必要时减仓或退出。无法判断时原则是保护本金，不靠猜测承担不可控风险。",
    "q36_45": "我理解胜率必须和赔率一起看，最大回撤决定策略能否承受。策略要有失效条件，不交易也是规则的一部分，情绪驱动、赔率不足、风险不可量化的钱不该赚。",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a full_assessment CLI submission with complete sample answers."
    )
    parser.add_argument("--user-id", default="cli_full_assessment_test")
    parser.add_argument("--no-llm", action="store_true", help="Skip Kimi and use local fallback scoring.")
    parser.add_argument("--keep-memory", action="store_true", help="Keep the temp memory JSON and print its path.")
    parser.add_argument("--show-report-json", action="store_true", help="Print the normalized report JSON.")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    answers = build_answers()

    with tempfile.TemporaryDirectory(prefix="ai_trading_assessment_") as tmpdir:
        memory_path = Path(tmpdir) / "memory_store.json"
        result = run_questionnaire_cli(
            answers=answers,
            memory_path=memory_path,
            user_id=args.user_id,
            no_llm=args.no_llm,
            timeout=args.timeout,
        )

        print_summary(result, answers, memory_path if args.keep_memory else None)
        if args.show_report_json:
            print(json.dumps(result["report"], ensure_ascii=False, indent=2))

        if args.keep_memory:
            kept_path = ROOT / "data" / f"{args.user_id}_full_assessment_cli_memory.json"
            kept_path.write_text(memory_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"kept_memory_copy={kept_path}")

    return 0


def build_answers() -> list[dict[str, str]]:
    sys.path.insert(0, str(ROOT))
    from backend.app.questionnaire_store import get_questionnaire

    questionnaire = get_questionnaire("full_assessment")
    question_ids = [question["id"] for question in questionnaire["questions"]]
    missing = [question_id for question_id in question_ids if question_id not in SAMPLE_ANSWERS]
    extra = sorted(set(SAMPLE_ANSWERS) - set(question_ids))
    if missing or extra:
        raise SystemExit(
            json.dumps(
                {"missing_sample_answers": missing, "extra_sample_answers": extra},
                ensure_ascii=False,
                indent=2,
            )
        )
    return [{"question_id": question_id, "answer": SAMPLE_ANSWERS[question_id]} for question_id in question_ids]


def run_questionnaire_cli(
    *,
    answers: list[dict[str, str]],
    memory_path: Path,
    user_id: str,
    no_llm: bool,
    timeout: int,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "backend.app.cli",
        "--memory-path",
        str(memory_path),
        "questionnaire",
        "submit",
        "--id",
        "full_assessment",
        "--user-id",
        user_id,
        "--answers-json",
        json.dumps(answers, ensure_ascii=False),
    ]
    if no_llm:
        cmd.append("--no-llm")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        print("CLI command failed.", file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        print(completed.stdout, file=sys.stderr)
        raise SystemExit(completed.returncode)
    return json.loads(completed.stdout)


def print_summary(result: dict[str, Any], answers: list[dict[str, str]], memory_path: Path | None) -> None:
    report = result["report"]
    trace = result.get("tool_trace", [])
    trace_status = {item.get("name"): item.get("status") for item in trace}
    answer_validate = next((item for item in trace if item.get("name") == "answer_validate"), {})
    kimi_trace = next((item for item in trace if item.get("name") == "kimi_profile_generate"), {})

    summary = {
        "questionnaire_id": result.get("questionnaire", {}).get("id"),
        "answer_count": len(answers),
        "empty_count": answer_validate.get("output_summary", {}).get("empty_count"),
        "kimi_status": kimi_trace.get("status"),
        "kimi_detail": kimi_trace.get("detail"),
        "schema_validate": trace_status.get("schema_validate"),
        "total_score": report.get("total_score"),
        "dimension_scores": report.get("dimension_scores"),
        "trader_type": report.get("trader_type"),
        "risk_level": report.get("risk_level"),
        "risk_tags": report.get("risk_tags"),
        "memory_written": result.get("memory_written"),
        "memory_path": str(memory_path) if memory_path else "(temporary, removed after run)",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())

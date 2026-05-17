import { useEffect, useRef, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import { Compliance } from "../components/Compliance.jsx";
import { Breadcrumb } from "../components/Breadcrumb.jsx";
import { KLineChart } from "../components/KLineChart.jsx";
import { getMarketKline, submitTrainingCheck } from "../api/backend.js";
import { CURRENT_USER_ID } from "../userSession.js";

const scenarios = [
  { id: "buy",    label: "我准备买入",       tag: "交易前",   Ic: Icon.Buy },
  { id: "hold",   label: "我已经持仓",       tag: "持仓中",   Ic: Icon.Hold },
  { id: "add",    label: "我想加仓",        tag: "持仓中",   Ic: Icon.AddPos },
  { id: "reduce", label: "我想减仓",        tag: "持仓中",   Ic: Icon.ReducePos },
  { id: "loss",   label: "亏损后想补仓",     tag: "高风险",   Ic: Icon.Loss },
  { id: "chase",  label: "看到上涨想追",     tag: "高风险",   Ic: Icon.Chase },
  { id: "check",  label: "检查交易计划",     tag: "交易前",   Ic: Icon.Check },
];

const scenarioLabelById = Object.fromEntries(scenarios.map((item) => [item.id, item.label]));

const initialDraft = {
  stock: "",
  position: "",
  reason: "",
  riskBoundary: "",
  holdingPeriod: "",
};

const POSITION_PERCENT_LABEL = "计划买入仓位(百分比)";

const requiredTrainingFields = [
  ["stock", "股票名称 / 代码"],
  ["reason", "买入理由"],
  ["riskBoundary", "风险边界"],
];

const optionalTrainingFields = [
  ["position", POSITION_PERCENT_LABEL],
  ["holdingPeriod", "预期持有周期"],
];

const placeholderFields = requiredTrainingFields.map(([, label]) => label);

const generationProgressStages = [
  { percent: 12, label: "解析交易计划" },
  { percent: 32, label: "导入股票上下文" },
  { percent: 56, label: "运行训练规则" },
  { percent: 78, label: "调用 Kimi 生成反馈" },
  { percent: 92, label: "写入长期交易记忆" },
];

function hasValue(value) {
  return String(value || "").trim().length > 0;
}

function unique(items) {
  return Array.from(new Set(items.filter(Boolean)));
}

function extractStockCode(value) {
  return String(value || "").match(/(?:^|\D)(\d{6})(?!\d)/)?.[1] || "";
}

function missingFieldsFromDraft(draft) {
  return requiredTrainingFields
    .filter(([key]) => !hasValue(draft[key]))
    .map(([, label]) => label);
}

function parsePositionPercent(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const normalized = raw.replace(/[％%]\s*$/, "").trim();
  if (!normalized) return Number.NaN;
  return Number(normalized);
}

function getPositionPercentError(value) {
  if (!hasValue(value)) return "";
  const parsed = parsePositionPercent(value);
  if (!Number.isFinite(parsed)) return `${POSITION_PERCENT_LABEL}只能填写数字`;
  if (parsed < 0 || parsed > 100) return `${POSITION_PERCENT_LABEL}需在 0-100 之间`;
  return "";
}

function normalizePositionPercent(value) {
  const parsed = parsePositionPercent(value);
  return Number.isFinite(parsed) ? `${parsed}%` : "";
}

function submitNoteTone(note) {
  return note.includes("本地") || note.includes("需在") || note.includes("只能") ? "warn" : "ok";
}

function riskTone(label) {
  if (label.includes("追涨") || label.includes("止损") || label.includes("补仓") || label.includes("报复") || label.includes("计划")) {
    return "red";
  }
  return "amber";
}

function extractLocalRisks(draft, missingFields) {
  const text = `${draft.reason} ${draft.riskBoundary}`;
  return unique([
    text.includes("涨") || text.includes("踏空") ? "追涨" : "",
    missingFields.includes("风险边界") ? "止损缺失" : "",
    missingFields.length >= 3 ? "计划缺失" : "",
    text.includes("报复") || text.includes("翻本") ? "报复性交易" : "",
  ]);
}

function buildFallbackTasks(missingFields, riskTags) {
  return unique([
    ...missingFields.map((field) => `补全${field}`),
    riskTags.includes("止损缺失") ? "写明判断错误时的处理方式、最大可接受亏损或逻辑失效条件" : "",
    riskTags.includes("追涨") ? "写出本次交易不是短期情绪驱动的证据" : "",
    riskTags.includes("报复性交易") ? "暂停加仓，先复盘亏损后的操作冲动" : "",
  ]).slice(0, 6);
}

function asList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function buildFallbackDecisionSupport(missingFields, riskTags, score) {
  if (missingFields.length) {
    return [`先补全${missingFields.join("、")}，再进入下一步计划检查。`];
  }
  if (score >= 75 && !riskTags.some((tag) => tag !== "暂无高风险标签")) {
    return ["计划关键字段已完整，下一步重点核对买入理由、风险边界与公开背景是否相互支持。"];
  }
  return ["先处理已识别的行为风险，再决定是否进入下一步观察。"];
}

function buildFallbackRiskWarnings(riskTags) {
  const warnings = {
    追涨: "识别到追涨风险，需确认买入理由不是由短期涨幅或踏空情绪触发。",
    消息驱动: "识别到消息驱动风险，需核对公告、新闻来源和可持续证据。",
    止损缺失: "识别到风险边界不足，需先写明判断错误时的处理方式。",
    仓位偏高: "识别到仓位偏高风险，需核对计划仓位是否匹配账户承受能力。",
    补仓冲动: "识别到补仓冲动风险，需区分计划内加仓条件和亏损后的情绪反应。",
    报复性交易: "识别到报复性交易风险，需先暂停并复盘亏损后的操作冲动。",
    计划缺失: "识别到计划缺失风险，需补全关键字段后再进行计划检查。",
  };
  const items = riskTags.filter((tag) => tag !== "暂无高风险标签").map((tag) => warnings[tag] || `识别到${tag}风险，需写出具体证据和约束条件。`);
  return items.length ? items : ["暂无高风险标签，仍需按已写明的风险边界检查执行前条件。"];
}

function buildFallbackResearchItems(report) {
  const sourceStatus = report.stock_context_summary?.source_status || {};
  const labels = {
    quote: "实时行情",
    kline: "近期K线与波动",
    announcements: "公司公告",
    news: "相关新闻",
    company_profile: "公司资料",
    reports: "研报摘要",
  };
  const missingSources = Object.entries(labels)
    .filter(([key]) => sourceStatus[key] && !sourceStatus[key].ok)
    .map(([, label]) => label);
  if (missingSources.length) {
    return [`补充核对${missingSources.slice(0, 3).join("、")}，避免只依赖单一题材或短期价格表现。`];
  }
  const hints = asList(report.stock_context_summary?.behavior_observation_hints);
  return hints.length ? hints : ["核对最新行情、公告、新闻和研报摘要，确认买入理由不是单一消息或短期波动驱动。"];
}

function buildFallbackPauseConditions(riskTags) {
  return unique([
    "触发已写明的风险边界时，暂停本次计划并记录触发原因。",
    "如果买入理由无法被公开资料或价格行为验证，暂停本次计划并补充研究。",
    riskTags[0] && riskTags[0] !== "暂无高风险标签" ? `当${riskTags[0]}风险继续升高且无法被计划约束时，暂停本次计划。` : "",
  ]).slice(0, 4);
}

function buildTrainingReport(draft, scenario, payload) {
  const report = payload?.report || {};
  const localMissingFields = missingFieldsFromDraft(draft);
  const missingFields = report.missing_fields?.length
    ? unique([...report.missing_fields, ...localMissingFields])
    : localMissingFields;
  const riskTags = report.risk_tags?.length ? report.risk_tags : extractLocalRisks(draft, missingFields);
  const completed = requiredTrainingFields.length - missingFields.length;
  const optionalCompleted = optionalTrainingFields.filter(([key]) => hasValue(draft[key])).length;
  const fallbackScore = Math.max(
    0,
    Math.min(
      100,
      Math.round((completed / requiredTrainingFields.length) * 75) + optionalCompleted * 5 - Math.min(30, riskTags.length * 6),
    ),
  );
  const score = report.plan_score ?? fallbackScore;
  const decision = report.training_decision || (score >= 75 ? "满足本次训练规则" : "当前不满足本次训练规则");
  const tasks = report.training_tasks?.length ? report.training_tasks : buildFallbackTasks(missingFields, riskTags);
  const decisionSupportAdvice = asList(report.decision_support_advice);
  const riskWarnings = asList(report.risk_warnings);
  const missingResearchItems = asList(report.missing_research_items);
  const planImprovementTasks = asList(report.plan_improvement_tasks);
  const pauseConditions = asList(report.pause_conditions);
  const reasons = unique([
    ...missingFields.map((field) => `缺少${field}`),
    ...riskTags.map((tag) => `识别到${tag}风险`),
    report.summary || "",
  ]).slice(0, 4);

  return {
    score,
    scenarioLabel: report.scenario_label || `${scenarioLabelById[report.scenario || scenario] || "行为训练"}场景`,
    decision,
    statusLabel: score >= 75 ? "计划完整度达标" : "计划完整度偏低",
    statusDetail: missingFields.length ? `需补全 ${missingFields.length} 项关键字段` : "关键字段已填写",
    verdictDetail: missingFields.length ? (report.next_requirement || `请先补全：${missingFields.join(" / ")}`) : "关键字段已填写，可进入下一步训练",
    riskTags: riskTags.length ? riskTags : ["暂无高风险标签"],
    missingFields,
    reasonsTitle: missingFields.length || riskTags.length ? "系统关注点" : "结果摘要",
    reasons: reasons.length ? reasons : ["交易计划关键字段已填写，继续保持按计划执行。"],
    tasks: tasks.length ? tasks : ["保持当前交易计划，并在交易后完成复盘记录"],
    decisionSupportAdvice: decisionSupportAdvice.length ? decisionSupportAdvice : buildFallbackDecisionSupport(missingFields, riskTags, score),
    riskWarnings: riskWarnings.length ? riskWarnings : buildFallbackRiskWarnings(riskTags),
    missingResearchItems: missingResearchItems.length ? missingResearchItems : buildFallbackResearchItems(report),
    planImprovementTasks: planImprovementTasks.length ? planImprovementTasks : tasks.slice(0, 4),
    pauseConditions: pauseConditions.length ? pauseConditions : buildFallbackPauseConditions(riskTags),
    toolCalls: payload?.tool_trace?.length ?? 0,
    memoryStatus: payload ? (payload.memory_written ? "已写入记忆" : "未写入记忆") : "本地预览",
    taskTitle: missingFields.length ? "请补全交易计划再提交" : "本次训练任务已生成",
  };
}

export function TrainingPage({ onNav }) {
  const [scenario, setScenario] = useState("buy");
  const [draft, setDraft] = useState(initialDraft);
  const [trainingResult, setTrainingResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitNote, setSubmitNote] = useState("");
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);
  const [generationProgress, setGenerationProgress] = useState({ percent: 0, label: "" });
  const [marketState, setMarketState] = useState({ status: "idle", payload: null, error: "" });
  const scenarioRef = useRef(null);
  const feedbackRef = useRef(null);
  const positionPercentError = getPositionPercentError(draft.position);
  const showPositionPercentError = Boolean(positionPercentError);
  const stockCode = extractStockCode(draft.stock);

  useEffect(() => {
    if (!stockCode) {
      setMarketState({ status: "idle", payload: null, error: "" });
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setMarketState((current) => ({ ...current, status: "loading", error: "" }));
      try {
        const payload = await getMarketKline({ symbol: stockCode, limit: 120, signal: controller.signal });
        setMarketState({ status: "ready", payload, error: "" });
      } catch (error) {
        if (error.name === "AbortError") return;
        setMarketState({ status: "error", payload: null, error: "行情背景暂不可用，训练提交不受影响。" });
      }
    }, 350);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [stockCode]);

  const scrollTo = (ref) => {
    window.requestAnimationFrame(() => {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const startScenarioSelection = () => scrollTo(scenarioRef);

  const updateDraft = (field) => (event) => {
    setDraft((current) => ({ ...current, [field]: event.target.value }));
    setTrainingResult(null);
    setSubmitNote("");
    setHasAttemptedSubmit(false);
    setGenerationProgress({ percent: 0, label: "" });
  };

  const requiredStyle = (field) => (hasAttemptedSubmit && !hasValue(draft[field]) ? { borderColor: "var(--danger)" } : undefined);

  const submitTraining = async (event) => {
    event.preventDefault();
    setHasAttemptedSubmit(true);
    setSubmitNote("");

    if (positionPercentError) {
      setTrainingResult(null);
      setSubmitNote(positionPercentError);
      setGenerationProgress({ percent: 0, label: "" });
      return;
    }

    setSubmitting(true);
    let progressIndex = 0;
    setGenerationProgress(generationProgressStages[progressIndex]);
    const progressTimer = window.setInterval(() => {
      progressIndex = Math.min(progressIndex + 1, generationProgressStages.length - 1);
      setGenerationProgress(generationProgressStages[progressIndex]);
    }, 700);

    const tradePlan = {
      stock: draft.stock,
      position: normalizePositionPercent(draft.position),
      reason: draft.reason,
      risk_boundary: draft.riskBoundary,
      holding_period: draft.holdingPeriod,
    };

    try {
      const payload = await submitTrainingCheck({
        userId: CURRENT_USER_ID,
        scenario,
        message: draft.reason,
        tradePlan,
        useLlm: true,
      });
      setTrainingResult(buildTrainingReport(draft, scenario, payload));
      setSubmitNote("训练反馈已生成，并写入长期交易记忆。");
    } catch {
      setTrainingResult(buildTrainingReport(draft, scenario));
      setSubmitNote("训练反馈已生成。本地预览模式下不会写入长期记忆。");
    } finally {
      window.clearInterval(progressTimer);
      setGenerationProgress({ percent: 100, label: "训练反馈生成完成" });
      setSubmitting(false);
      window.setTimeout(() => {
        setGenerationProgress({ percent: 0, label: "" });
      }, 900);
      scrollTo(feedbackRef);
    }
  };

  const adviceGroups = trainingResult ? [
    ["建议检查", trainingResult.decisionSupportAdvice],
    ["风险提醒", trainingResult.riskWarnings],
    ["还需补充资料", trainingResult.missingResearchItems],
    ["计划补强", trainingResult.planImprovementTasks],
    ["暂停条件", trainingResult.pauseConditions],
  ].filter(([, items]) => items?.length) : [];

  return (
    <div className="page" data-screen-label="03 行为训练">
      <Breadcrumb items={[{ label: "工作台", to: "home" }, { label: "AI 行为训练" }]} onNav={onNav}/>

      <section className="sub-hero">
        <div>
          <div className="eyebrow"><span className="bar"></span>02 · TRAINING ENGINE</div>
          <h1>交易前一次<span className="hl-inline">“规则化体检”</span>，<br/>挡住你的冲动操作。</h1>
          <p className="lede">
            AI 行为训练引擎在交易前或持仓中介入，检查你的交易计划完整度、识别行为风险，并生成下一步必须完成的训练任务 —— 把知识转为可落地的执行动作。
          </p>
          <div className="sub-hero-actions">
            <button className="btn btn-blue" onClick={startScenarioSelection}>
              选择场景开始训练 <Icon.Arrow size={14}/>
            </button>
          </div>
          <div className="sub-hero-meta">
            <div className="sub-meta-item">
              <div className="l">场景模板</div>
              <div className="v">7 种交易情境</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">风险标签</div>
              <div className="v">FOMO / 追涨 / 补仓等</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">输出</div>
              <div className="v">训练反馈 + 行为约束</div>
            </div>
          </div>
        </div>

        {/* Right: live scoring card */}
        <div className="tp-livecard">
          <div className="lc-head">{trainingResult ? "BEHAVIOR TRAINING · LIVE" : "BEHAVIOR TRAINING · READY"}</div>
          {trainingResult ? (
            <>
              <div className="lc-score-row">
                <div className="lc-score">{trainingResult.score}<span className="of"> / 100</span></div>
                <div className="lc-status">
                  <div className="v">{trainingResult.statusLabel}</div>
                  <div className="l">{trainingResult.statusDetail}</div>
                </div>
              </div>

              <div className="lc-tags">
                {trainingResult.riskTags.map((tag) => (
                  <span className={`tag ${riskTone(tag)}`} key={tag}>{tag}</span>
                ))}
              </div>

              <div className="lc-verdict">
                <div className="ll">系统判断</div>
                <div className="lh">{trainingResult.decision}</div>
                <div className="ld">{trainingResult.verdictDetail}</div>
              </div>

              <div className="lc-foot">
                <span>tool_trace: {trainingResult.toolCalls} calls</span>
                <span className="ok">✓ {trainingResult.memoryStatus}</span>
              </div>
            </>
          ) : (
            <>
              <div className="lc-ready">
                <div className="lc-ready-title">等待提交训练计划</div>
                <p>选择场景并填写交易计划后，系统将生成完整度、风险标签与训练任务。</p>
              </div>

              <div className="lc-verdict neutral">
                <div className="ll">待生成</div>
                <div className="lh">尚未提交训练计划</div>
                <div className="ld">提交前不会展示评分、风险判断或记忆写入状态。</div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* Scenarios */}
      <section className="section" ref={scenarioRef}>
        <div className="section-eyebrow">
          <span className="num mono">02</span>
          <h2>选择当前所处的交易场景</h2>
        </div>
        <div className="scenarios">
          {scenarios.map(s => (
            <button
              key={s.id}
              className={`scenario ${scenario === s.id ? "active" : ""}`}
              onClick={() => {
                setScenario(s.id);
                setTrainingResult(null);
                setSubmitNote("");
                setHasAttemptedSubmit(false);
                setGenerationProgress({ percent: 0, label: "" });
              }}
            >
              <div className="s-icon"><s.Ic/></div>
              <div className="s-label">{s.label}</div>
              <div className="s-tag">{s.tag}</div>
            </button>
          ))}
        </div>

        {/* Form + Feedback preview */}
        <div className="training-preview">
          <div className="training-left-stack">
          <form className="tp-form" onSubmit={submitTraining}>
            <h3>交易计划填写</h3>
            <div className="sub">只填写建仓前必要信息，系统会自动补充公开背景资料</div>

            <div className="tp-row">
              <div className="tp-field">
                <label>股票名称 / 代码 <span className="req">必填</span></label>
                <input value={draft.stock} onChange={updateDraft("stock")} placeholder="请输入股票名称或代码" style={requiredStyle("stock")}/>
              </div>
              <div className="tp-field">
                <label>{POSITION_PERCENT_LABEL} <span className="opt">选填</span></label>
                <input
                  value={draft.position}
                  onChange={updateDraft("position")}
                  placeholder="例如：20，表示总资金的 20%"
                  inputMode="decimal"
                  aria-invalid={showPositionPercentError ? "true" : "false"}
                  style={showPositionPercentError ? { borderColor: "var(--danger)" } : undefined}
                />
                {showPositionPercentError && (
                  <div className="field-error">{positionPercentError}</div>
                )}
              </div>
            </div>

            <div className="tp-field">
              <label>买入理由 <span className="req">必填</span></label>
              <textarea rows="3" value={draft.reason} onChange={updateDraft("reason")} placeholder="你为什么想买？例如：业绩改善、政策催化、突破平台、估值修复等" style={requiredStyle("reason")}></textarea>
            </div>

            <div className="tp-field">
              <label>风险边界 <span className="req">必填</span></label>
              <textarea
                rows="3"
                value={draft.riskBoundary}
                onChange={updateDraft("riskBoundary")}
                placeholder="如果判断错了怎么办？写明最大可接受亏损、止损触发条件或交易逻辑失效条件"
                style={requiredStyle("riskBoundary")}
              ></textarea>
            </div>

            <div className="tp-row">
              <div className="tp-field">
                <label>预期持有周期 <span className="opt">选填</span></label>
                <select value={draft.holdingPeriod} onChange={updateDraft("holdingPeriod")}>
                  <option value="" disabled>请选择...</option>
                  <option>日内</option>
                  <option>1-3 天</option>
                  <option>1-2 周</option>
                  <option>1 个月以上</option>
                  <option>不确定</option>
                </select>
              </div>
            </div>

            <button className="submit" type="submit" disabled={submitting}>
              {submitting ? "训练中..." : "提交训练 · 调用 training_engine"}
            </button>
            {generationProgress.percent > 0 && (
              <div className="training-progress" aria-live="polite">
                <div className="training-progress-head">
                  <span>{generationProgress.label}</span>
                  <span className="mono">{generationProgress.percent}%</span>
                </div>
                <div className="training-progress-track">
                  <span style={{ width: `${generationProgress.percent}%` }}></span>
                </div>
              </div>
            )}
            {submitNote && (
              <div className={`training-submit-note ${submitNoteTone(submitNote)}`}>
                {submitNote}
              </div>
            )}
          </form>

          <KLineChart
            status={marketState.status}
            payload={marketState.payload}
            error={marketState.error}
          />
          </div>

          {/* Feedback panel - dark */}
          <div className="tp-feedback" ref={feedbackRef}>
            {trainingResult ? (
              <>
                <div className="fb-head">
                  <div>
                    <div className="fb-title">AI 交易训练反馈</div>
                    <div className="fb-h">{trainingResult.scenarioLabel} · 训练结果</div>
                  </div>
                  <div>
                    <div className="fb-score mono">{trainingResult.score}<span className="of">/100</span></div>
                  </div>
                </div>

                <div className="fb-status">
                  <Icon.Warn size={14}/> {trainingResult.decision}
                </div>

                <div className="fb-section">
                  <h5>{trainingResult.reasonsTitle}</h5>
                  <ol className="fb-reasons">
                    {trainingResult.reasons.map((item) => <li key={item}>{item}</li>)}
                  </ol>
                </div>

                <div className="fb-section">
                  <h5>行为风险标签</h5>
                  <div className="fb-tags">
                    {trainingResult.riskTags.map((tag) => <span className="fb-tag" key={tag}>{tag}</span>)}
                  </div>
                </div>

                <div className="fb-section fb-advice">
                  <h5>买入前决策支持</h5>
                  <div className="fb-advice-list">
                    {adviceGroups.map(([title, items]) => (
                      <div className="fb-advice-block" key={title}>
                        <div className="fb-advice-title">{title}</div>
                        <ul>
                          {items.map((item) => <li key={`${title}-${item}`}>{item}</li>)}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="fb-task">
                  <div className="ft-l">本次训练任务</div>
                  <div className="ft-h">{trainingResult.taskTitle}</div>
                  <ul>
                    {trainingResult.tasks.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              </>
            ) : (
              <>
                <div className="fb-head">
                  <div>
                    <div className="fb-title">AI 交易训练反馈</div>
                    <div className="fb-h">尚未生成训练结果</div>
                  </div>
                </div>

                <div className="fb-status pending">
                  <Icon.Check/> 等待提交训练计划
                </div>

                <div className="fb-task placeholder">
                  <div className="ft-l">提交前请完成</div>
                  <div className="ft-h">请选择场景并填写交易计划</div>
                  <ul>
                    {placeholderFields.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      <Compliance/>
    </div>
  );
}

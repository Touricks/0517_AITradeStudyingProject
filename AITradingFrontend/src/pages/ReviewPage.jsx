import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import { Compliance } from "../components/Compliance.jsx";
import { Breadcrumb } from "../components/Breadcrumb.jsx";
import { getMemorySnapshot, submitReviewRun } from "../api/backend.js";
import { CURRENT_USER_ID } from "../userSession.js";

const initialDraft = {
  stock: "",
  buyDate: "",
  sellDate: "",
  buyPrice: "",
  sellPrice: "",
  position: "",
  buyReason: "",
  sellReason: "",
  stopLossPlan: "",
  followedPlan: "",
  changedPlan: "",
  emotion: "",
  result: "",
  reflection: "",
};

const requiredReviewFields = [
  ["stock", "股票名称 / 代码"],
  ["buyReason", "买入理由"],
  ["stopLossPlan", "止损计划"],
  ["followedPlan", "原计划执行"],
  ["reflection", "自我总结"],
];

function mistakeTone(label) {
  if (label.includes("计划") || label.includes("止损") || label.includes("仓位")) return "red";
  return "amber";
}

function scoreColor(score) {
  if (score < 50) return "var(--danger)";
  if (score < 70) return "var(--warn)";
  return "var(--success)";
}

function reviewLevel(score) {
  if (score >= 75) return "good";
  if (score >= 55) return "mid";
  return "bad";
}

function buildTradeRecord(draft) {
  return {
    stock: draft.stock,
    buy_date: draft.buyDate,
    sell_date: draft.sellDate,
    buy_price: draft.buyPrice,
    sell_price: draft.sellPrice,
    position: draft.position,
    buy_reason: draft.buyReason,
    sell_reason: draft.sellReason,
    stop_loss_plan: draft.stopLossPlan,
    followed_plan: draft.followedPlan,
    changed_plan: draft.changedPlan,
    emotion: draft.emotion,
    result: draft.result,
  };
}

function buildLocalReport(draft, payload) {
  const report = payload?.report || {};
  const memory = payload?.memory || {};
  const mistakes = report.mistake_types?.length
    ? report.mistake_types
    : [
        !draft.stopLossPlan ? "计划缺失" : "",
        draft.followedPlan === "no" ? "止损不执行" : "",
        draft.emotion.includes("害怕") || draft.emotion.includes("踏空") ? "情绪驱动" : "",
      ].filter(Boolean);
  const repeated = report.repeated_patterns?.length
    ? `重复出现：${report.repeated_patterns.join("、")}。`
    : "本次复盘已与历史交易记忆比对，暂未发现新的高频重复模式。";

  return {
    id: (report.report_id || "T_LOCAL").replace(/^review_?/, "T_").slice(0, 12).toUpperCase(),
    stock: report.trade_document?.stock || draft.stock,
    dateLine: `买入 ${draft.buyDate || "--"} · 卖出 ${draft.sellDate || "--"} · 仓位 ${draft.position || "--"}% · ${draft.result || "结果待记录"}`,
    score: report.review_score ?? (draft.stopLossPlan && draft.followedPlan === "yes" ? 78 : 52),
    rootCause: report.root_cause || "本次问题集中在交易前计划完整度与盘中执行一致性，需要把止损、退出条件和复盘时间提前写清。",
    mistakeTypes: mistakes.length ? mistakes : ["需要更多样本"],
    repeatedPattern: repeated,
    rules: report.new_rules?.length
      ? report.new_rules
      : [
          "未来 3 笔交易必须在买入前填写入场理由、止损计划、退出条件和复盘时间。",
          "亏损触及预设条件时先复盘计划，不在盘中临时扩大亏损边界。",
          "当前阶段优先训练规则执行，不以单笔盈亏评价能力。",
        ],
    memoryId: memory.memory_id || "local_preview",
    memoryStatus: payload?.memory_written ? "已写入长期记忆" : "本地复盘预览",
  };
}

function timelineFromReport(report) {
  if (!report) return null;
  const score = Number(report.score ?? report.review_score ?? 0);
  const tradeDocument = report.trade_document || {};
  const mistakeTypes = report.mistakeTypes || report.mistake_types || [];
  return {
    date: report.created_at ? report.created_at.slice(0, 10) : "刚刚",
    name: report.stock || tradeDocument.stock || "未命名交易",
    meta: [report.dateLine || report.summary || "复盘报告已生成"].filter(Boolean),
    cause: mistakeTypes.length ? mistakeTypes.join(" · ") : "等待更多复盘样本",
    score,
    level: reviewLevel(score),
  };
}

function timelineFromMemoryRecord(record) {
  const score = Number(record.review_score ?? 0);
  const tradeDocument = record.trade_document || {};
  const mistakeTypes = record.mistake_types || [];
  return {
    date: record.created_at ? record.created_at.slice(0, 10) : "--",
    name: tradeDocument.stock || record.stock || "未命名交易",
    meta: [record.summary || "复盘报告"].filter(Boolean),
    cause: mistakeTypes.length ? mistakeTypes.join(" · ") : "暂无错误归因",
    score,
    level: reviewLevel(score),
  };
}

export function ReviewPage({ onNav }) {
  const formRef = useRef(null);
  const reportRef = useRef(null);
  const [draft, setDraft] = useState(initialDraft);
  const [report, setReport] = useState(null);
  const [recentReviews, setRecentReviews] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitNote, setSubmitNote] = useState("");

  const missingFields = useMemo(
    () => requiredReviewFields.filter(([key]) => !String(draft[key] || "").trim()),
    [draft],
  );
  const hasDraftInput = useMemo(
    () => Object.values(draft).some((value) => String(value || "").trim()),
    [draft],
  );
  const reviewInputScore = hasDraftInput ? Math.max(0, 100 - missingFields.length * 14) : null;
  const errors = useMemo(() => {
    const counts = new Map();
    for (const item of recentReviews) {
      for (const label of String(item.cause || "").split(/ · |、|,|，/).map((part) => part.trim()).filter(Boolean)) {
        if (label.includes("暂无") || label.includes("等待")) continue;
        counts.set(label, (counts.get(label) || 0) + 1);
      }
    }
    return Array.from(counts, ([name, count]) => ({
      name,
      count,
      size: count >= 3 ? "lg" : count >= 2 ? "md" : "",
    }));
  }, [recentReviews]);

  useEffect(() => {
    let cancelled = false;
    async function loadReviewHistory() {
      try {
        const memory = await getMemorySnapshot();
        if (cancelled) return;
        const reviews = (memory.review_reports || [])
          .filter((item) => item.user_id === CURRENT_USER_ID)
          .map(timelineFromMemoryRecord);
        setRecentReviews(reviews);
      } catch {
        if (!cancelled) setRecentReviews([]);
      }
    }
    loadReviewHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollTo = (ref) => {
    window.requestAnimationFrame(() => {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const startNewReview = () => {
    setSubmitNote("");
    scrollTo(formRef);
  };

  const updateDraft = (field) => (event) => {
    setDraft((current) => ({ ...current, [field]: event.target.value }));
    setReport(null);
    setSubmitNote("");
  };

  const submitReview = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitNote("");

    try {
      const payload = await submitReviewRun({
        userId: CURRENT_USER_ID,
        useLlm: true,
        selfReflection: draft.reflection,
        tradeRecord: buildTradeRecord(draft),
      });
      const nextReport = buildLocalReport(draft, payload);
      setReport(nextReport);
      setRecentReviews((current) => [timelineFromReport(nextReport), ...current].filter(Boolean));
      setSubmitNote("复盘报告已生成，并写入长期交易记忆。");
    } catch {
      const nextReport = buildLocalReport(draft);
      setReport(nextReport);
      setRecentReviews((current) => [timelineFromReport(nextReport), ...current].filter(Boolean));
      setSubmitNote("复盘报告已生成。本地预览模式下不会写入长期记忆。");
    } finally {
      setSubmitting(false);
      scrollTo(reportRef);
    }
  };

  const reviewScoreColor = report ? scoreColor(report.score) : "var(--ink-300)";

  return (
    <div className="page" data-screen-label="04 智能复盘">
      <Breadcrumb items={[{ label: "工作台", to: "home" }, { label: "AI 智能复盘" }]} onNav={onNav}/>

      <section className="sub-hero">
        <div>
          <div className="eyebrow"><span className="bar"></span>03 · REVIEW ENGINE</div>
          <h1>每一笔交易都成为<br/><span className="hl-inline">下一次训练的输入</span>。</h1>
          <p className="lede">
            AI 智能复盘引擎自动还原交易过程，对比计划与实际行为，识别错误归因与历史重复模式，并把新规则写入长期交易记忆 —— 让能力随时间持续进化。
          </p>
          <div className="sub-hero-actions">
            <button className="btn btn-blue" onClick={startNewReview}>
              新建复盘 <Icon.Arrow size={14}/>
            </button>
          </div>
          <div className="sub-hero-meta">
            <div className="sub-meta-item">
              <div className="l">错误分类</div>
              <div className="v">10 类行为模式</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">历史匹配</div>
              <div className="v">重复模式预警</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">输出</div>
              <div className="v">复盘报告 + 新规则</div>
            </div>
          </div>
        </div>

        {/* Review report */}
        <div className="review-report" ref={reportRef}>
          {report ? (
            <>
              <div className="rr-head">
                <div>
                  <div className="rr-ttl">REVIEW REPORT · {report.id}</div>
                  <div className="rr-stock">{report.stock}</div>
                  <div className="rr-date">{report.dateLine}</div>
                </div>
                <div className="rr-score-circle">
                  <svg viewBox="0 0 80 80">
                    <circle cx="40" cy="40" r="34" fill="none" stroke="#F2F4F9" strokeWidth="6"/>
                    <circle cx="40" cy="40" r="34" fill="none" stroke={reviewScoreColor} strokeWidth="6"
                      strokeDasharray={`${(report.score/100) * 213.6} 213.6`} strokeLinecap="round"/>
                  </svg>
                  <div className="v" style={{ color: reviewScoreColor }}>{report.score}</div>
                </div>
              </div>
              <div className="rr-body">
                <div className="rr-block">
                  <h5>复盘结论</h5>
                  <div className="rr-conclusion">
                    {report.rootCause}
                  </div>
                </div>

                <div className="rr-block">
                  <h5>错误归因</h5>
                  <div className="rr-tags">
                    {report.mistakeTypes.map((item) => (
                      <span className={`tag ${mistakeTone(item)}`} key={item}>{item}</span>
                    ))}
                  </div>
                </div>

                <div className="rr-block">
                  <h5>历史重复模式</h5>
                  <div style={{ fontSize: 13, color: "var(--ink-500)", padding: "10px 12px", background: "rgba(220,38,38,0.06)", borderRadius: 8, borderLeft: "3px solid var(--danger)" }}>
                    {report.repeatedPattern}
                  </div>
                </div>

                <div className="rr-block">
                  <h5>系统为你生成的新规则</h5>
                  <ol className="rr-rules">
                    {report.rules.map((item) => <li key={item}>{item}</li>)}
                  </ol>
                </div>

                <div style={{ marginTop: 18, padding: "12px 14px", background: "var(--surface-2)", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: "var(--ink-500)" }}>
                  <span className="mono">✓ session_memory_write · {report.memoryStatus}</span>
                  <span className="mono">memory_id: {report.memoryId}</span>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="rr-head">
                <div>
                  <div className="rr-ttl">REVIEW REPORT · READY</div>
                  <div className="rr-stock">暂无复盘报告</div>
                  <div className="rr-date">输入一笔交易后生成复盘结论、错误归因与新规则</div>
                </div>
              </div>
              <div className="rr-body">
                <div className="review-empty">
                  <div className="review-empty-title">等待提交复盘</div>
                  <p>提交前不会展示评分、历史重复模式或记忆写入状态。</p>
                  <ul>
                    <li>填写交易计划与实际执行</li>
                    <li>补充止损计划和自我总结</li>
                    <li>生成复盘报告后写入长期记忆</li>
                  </ul>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* New review form */}
      <section className="section" ref={formRef}>
        <div className="section-eyebrow">
          <span className="num mono">02</span>
          <h2>输入本次交易 · 生成复盘报告</h2>
        </div>
        <div className="review-workbench">
          <form className="tp-form review-form" onSubmit={submitReview}>
            <h3>交易记录</h3>
            <div className="sub">计划、执行、情绪和结果会一起进入复盘引擎</div>

            <div className="tp-row">
              <div className="tp-field">
                <label>股票名称 / 代码 <span className="req">必填</span></label>
                <input value={draft.stock} onChange={updateDraft("stock")} placeholder="请输入股票名称或代码" />
              </div>
              <div className="tp-field">
                <label>仓位比例</label>
                <input value={draft.position} onChange={updateDraft("position")} placeholder="请输入仓位比例" />
              </div>
            </div>

            <div className="tp-row">
              <div className="tp-field">
                <label>买入日期</label>
                <input value={draft.buyDate} onChange={updateDraft("buyDate")} placeholder="请输入买入日期" />
              </div>
              <div className="tp-field">
                <label>卖出日期</label>
                <input value={draft.sellDate} onChange={updateDraft("sellDate")} placeholder="请输入卖出日期" />
              </div>
            </div>

            <div className="tp-row">
              <div className="tp-field">
                <label>买入价</label>
                <input value={draft.buyPrice} onChange={updateDraft("buyPrice")} placeholder="请输入买入价" />
              </div>
              <div className="tp-field">
                <label>卖出价</label>
                <input value={draft.sellPrice} onChange={updateDraft("sellPrice")} placeholder="请输入卖出价" />
              </div>
            </div>

            <div className="tp-field">
              <label>买入理由 <span className="req">必填</span></label>
              <textarea rows="2" value={draft.buyReason} onChange={updateDraft("buyReason")} placeholder="请输入买入理由" />
            </div>

            <div className="tp-field">
              <label>止损计划 <span className="req">必填</span></label>
              <input value={draft.stopLossPlan} onChange={updateDraft("stopLossPlan")} placeholder="例如：跌破买入逻辑失效位置即退出" />
            </div>

            <div className="tp-row">
              <div className="tp-field">
                <label>原计划是否执行 <span className="req">必填</span></label>
                <select value={draft.followedPlan} onChange={updateDraft("followedPlan")}>
                  <option value="" disabled>请选择...</option>
                  <option value="yes">已执行</option>
                  <option value="no">未执行</option>
                </select>
              </div>
              <div className="tp-field">
                <label>是否临时改变计划</label>
                <select value={draft.changedPlan} onChange={updateDraft("changedPlan")}>
                  <option value="" disabled>请选择...</option>
                  <option value="yes">是</option>
                  <option value="no">否</option>
                </select>
              </div>
            </div>

            <div className="tp-row">
              <div className="tp-field">
                <label>卖出理由</label>
                <input value={draft.sellReason} onChange={updateDraft("sellReason")} placeholder="请输入卖出理由" />
              </div>
              <div className="tp-field">
                <label>交易结果</label>
                <input value={draft.result} onChange={updateDraft("result")} placeholder="请输入交易结果" />
              </div>
            </div>

            <div className="tp-field">
              <label>当时情绪状态</label>
              <select value={draft.emotion} onChange={updateDraft("emotion")}>
                <option value="" disabled>请选择...</option>
                <option>平稳</option>
                <option>害怕</option>
                <option>兴奋 · 担心踏空</option>
                <option>报复性 · 想翻本</option>
                <option>懊悔 · 想追回</option>
              </select>
            </div>

            <div className="tp-field">
              <label>自我总结 <span className="req">必填</span></label>
              <textarea rows="3" value={draft.reflection} onChange={updateDraft("reflection")} placeholder="请输入本次交易复盘总结" />
            </div>

            <button className="submit" disabled={submitting}>
              {submitting ? "生成中..." : "生成复盘 · 调用 review_engine"}
            </button>
            {submitNote && (
              <div className={`review-submit-note ${submitNote.includes("本地") ? "warn" : "ok"}`}>
                {submitNote}
              </div>
            )}
          </form>

          <div className="review-side">
            <div className="review-side-head">
              <div className="mono">REVIEW INPUT</div>
              <span className={`tag ${missingFields.length ? "amber" : "green"}`}>
                {missingFields.length ? `缺少 ${missingFields.length} 项` : "输入完整"}
              </span>
            </div>
            <div className="review-score-preview">
              <div className="v">{reviewInputScore == null ? "--" : reviewInputScore}</div>
              <div>
                <div className="h">复盘输入完整度</div>
                <p>完整记录交易前计划与盘中执行，系统才能区分“信息不足”和“行为偏离”。</p>
              </div>
            </div>
            <div className="review-field-list">
              {requiredReviewFields.map(([key, label]) => {
                const done = !missingFields.some(([missingKey]) => missingKey === key);
                return (
                  <div className={`review-field-status ${done ? "done" : ""}`} key={key}>
                    <span className="dot"></span>
                    <span>{label}</span>
                    <strong>{done ? "已填写" : "待补全"}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* Process Flow */}
      <section className="section">
        <div className="section-eyebrow">
          <span className="num mono">03</span>
          <h2>复盘流程 · 从一次交易到一条新规则</h2>
        </div>
        <div className="process-flow">
          <div className="pf-step">
            <div className="num">STEP 01</div>
            <div className="ic">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <path d="M14 2v6h6"/>
                <path d="M8 13h8M8 17h5"/>
              </svg>
            </div>
            <h4>输入交易</h4>
            <p>填写买入卖出时间、价格、仓位、原计划与实际行为、当时情绪状态。</p>
          </div>
          <div className="pf-step">
            <div className="num">STEP 02</div>
            <div className="ic">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.3-4.3"/>
              </svg>
            </div>
            <h4>AI 引擎分析</h4>
            <p>review_engine 还原交易过程，对比原计划与实际行为，识别偏离点。</p>
          </div>
          <div className="pf-step">
            <div className="num">STEP 03</div>
            <div className="ic">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 1 0 9-9"/>
                <path d="M3 3v6h6"/>
              </svg>
            </div>
            <h4>历史模式匹配</h4>
            <p>查询 session memory，标记是否与历史错误模式重复出现。</p>
          </div>
          <div className="pf-step">
            <div className="num">STEP 04</div>
            <div className="ic">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
            </div>
            <h4>规则化写入</h4>
            <p>输出复盘评分、错误归因、新规则，并写入用户长期记忆，约束下一笔交易。</p>
          </div>
        </div>
      </section>

      {/* Error types */}
      <section className="section">
        <div className="section-eyebrow">
          <span className="num mono">04</span>
          <h2>10 类错误行为 · 来自真实交易记录</h2>
        </div>
        {errors.length ? (
          <div className="error-types">
            <div className="error-cloud">
              {errors.map(e => (
                <span key={e.name} className={`error-chip ${e.size}`}>
                  {e.name} <span className="ct mono">×{e.count}</span>
                </span>
              ))}
            </div>
            <div className="card" style={{ background: "var(--warn-soft)", borderColor: "transparent" }}>
              <span className="tag amber">高频错误 · 当前记录</span>
              <h3 style={{ marginTop: 14, fontSize: 18, color: "var(--warn)" }}>{errors[0].name}</h3>
              <p style={{ fontSize: 13, color: "var(--ink-700)", lineHeight: 1.6, marginTop: 10, marginBottom: 0 }}>
                系统会根据真实复盘记录聚合高频行为错误，并推荐后续训练入口。
              </p>
              <button className="btn btn-blue" style={{ marginTop: 18, width: "100%" }} onClick={() => onNav("training")}>
                进入针对性训练 <Icon.Arrow size={14}/>
              </button>
            </div>
          </div>
        ) : (
          <div className="card empty-card">
            <h3>暂无错误分类</h3>
            <p>完成至少一笔复盘后，这里会基于真实记录聚合错误行为。</p>
          </div>
        )}
      </section>

      {/* Recent reviews timeline */}
      <section className="section">
        <div className="section-eyebrow">
          <span className="num mono">05</span>
          <h2>最近复盘</h2>
        </div>
        <div className="card" style={{ padding: "8px 28px" }}>
          {recentReviews.length ? (
            <div className="timeline">
              {recentReviews.map((r, i) => (
                <div className="tl-row" key={`${r.date}-${r.name}-${i}`}>
                  <div className="tl-date">{r.date}</div>
                  <div className="tl-content">
                    <div className="tl-name">{r.name}</div>
                    <div className="tl-meta">
                      {r.meta.map((m, j) => <span key={j}>{m}</span>)}
                      <span style={{ color: "var(--ink-500)" }}>· {r.cause}</span>
                    </div>
                  </div>
                  <div className={`tl-score mono ${r.level}`}>{r.score}<span style={{ fontSize: 12, color: "var(--ink-300)", fontWeight: 500 }}>/100</span></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-card timeline-empty">
              <h3>暂无历史复盘</h3>
              <p>提交第一笔复盘后，历史记录会在这里沉淀为长期交易记忆。</p>
            </div>
          )}
        </div>
      </section>

      <Compliance/>
    </div>
  );
}

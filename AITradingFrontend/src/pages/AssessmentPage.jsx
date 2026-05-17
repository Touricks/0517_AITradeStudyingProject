import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import { Compliance } from "../components/Compliance.jsx";
import { Breadcrumb } from "../components/Breadcrumb.jsx";
import { RadarChart } from "../components/RadarChart.jsx";
import { getFullAssessment, getMemorySnapshot, submitFullAssessment } from "../api/backend.js";
import { CURRENT_USER_ID } from "../userSession.js";
import {
  advanceProfileGenerationProgress,
  completeProfileGenerationProgress,
  failProfileGenerationProgress,
  idleProfileGenerationProgress,
  startProfileGenerationProgress,
} from "../services/profileGenerationProgress.js";

const DIMENSIONS = [
  { key: "market_understanding", num: "D1", name: "市场理解", desc: "是否理解不确定性、概率、周期与情绪" },
  { key: "analysis_framework", num: "D2", name: "分析框架", desc: "是否有稳定可重复的判断逻辑" },
  { key: "risk_control", num: "D3", name: "风险控制", desc: "是否先想『亏多少』，再想『赚多少』" },
  { key: "execution_discipline", num: "D4", name: "执行纪律", desc: "是否能严格按计划交易、不临时改单" },
  { key: "review_ability", num: "D5", name: "复盘能力", desc: "是否能从错误中提炼下一次规则" },
];

function scoreOf(report, key) {
  const raw = report?.dimension_scores?.[key];
  const value = Number(raw ?? 0);
  return Math.max(0, Math.min(20, Number.isFinite(value) ? value : 0));
}

function sectionForQuestion(sections, questionId) {
  return sections.find((section) => (section.question_ids ?? []).includes(questionId));
}

export function AssessmentPage({ onNav }) {
  const [questionnaire, setQuestionnaire] = useState(null);
  const [loadState, setLoadState] = useState("loading");
  const [error, setError] = useState("");
  const [started, setStarted] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answersById, setAnswersById] = useState({});
  const [submitState, setSubmitState] = useState("idle");
  const [result, setResult] = useState(null);
  const [storedProfile, setStoredProfile] = useState(null);
  const [generationProgress, setGenerationProgress] = useState(() => idleProfileGenerationProgress());
  const questionRef = useRef(null);

  const questions = questionnaire?.questions ?? [];
  const sections = questionnaire?.sections ?? [];
  const currentQuestion = questions[currentIndex];
  const report = result?.report;
  const profileReport = report || storedProfile;
  const hasProfile = Boolean(profileReport);
  const answeredCount = questions.filter((question) => (answersById[question.id] ?? "").trim()).length;
  const progressPct = questions.length ? ((currentIndex + 1) / questions.length) * 100 : 0;
  const currentSection = currentQuestion ? sectionForQuestion(sections, currentQuestion.id) : null;

  const dimensions = useMemo(
    () => DIMENSIONS.map((item) => ({ ...item, v: scoreOf(profileReport, item.key) })),
    [profileReport]
  );

  const sectionStats = useMemo(
    () => sections.map((section) => {
      const ids = section.question_ids ?? [];
      const done = ids.filter((id) => (answersById[id] ?? "").trim()).length;
      return { ...section, done, total: ids.length };
    }),
    [sections, answersById]
  );

  async function loadQuestionnaire() {
    setLoadState("loading");
    setError("");
    try {
      const data = await getFullAssessment();
      setQuestionnaire(data);
      setLoadState("ready");
    } catch (err) {
      setError(err.data?.detail || err.message || "问卷加载失败");
      setLoadState("error");
    }
  }

  useEffect(() => {
    loadQuestionnaire();
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadStoredProfile() {
      try {
        const memory = await getMemorySnapshot();
        if (!cancelled) {
          setStoredProfile(memory.user_profiles?.[CURRENT_USER_ID] || null);
        }
      } catch {
        if (!cancelled) setStoredProfile(null);
      }
    }
    loadStoredProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (submitState !== "submitting") return undefined;
    const timer = window.setInterval(() => {
      setGenerationProgress((progress) => advanceProfileGenerationProgress(progress));
    }, 700);
    return () => window.clearInterval(timer);
  }, [submitState]);

  const startFullAssessment = () => {
    setStarted(true);
    setResult(null);
    setSubmitState("idle");
    setGenerationProgress(idleProfileGenerationProgress());
    setCurrentIndex(0);
    window.requestAnimationFrame(() => {
      questionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const updateAnswer = (value) => {
    if (!currentQuestion) return;
    setStarted(true);
    setSubmitState("idle");
    setAnswersById((prev) => ({ ...prev, [currentQuestion.id]: value }));
  };

  const goNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      return;
    }
    submitAnswers();
  };

  const goPrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const jumpToQuestion = (questionId) => {
    const index = questions.findIndex((question) => question.id === questionId);
    if (index >= 0) {
      setStarted(true);
      setCurrentIndex(index);
      window.requestAnimationFrame(() => {
        questionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  };

  const submitAnswers = async () => {
    if (!questions.length || submitState === "submitting") return;
    setSubmitState("submitting");
    setError("");
    const answers = questions.map((question) => ({
      question_id: question.id,
      answer: answersById[question.id] ?? "",
    }));
    setGenerationProgress(startProfileGenerationProgress({ answerCount: answers.length }));
    try {
      const data = await submitFullAssessment({
        userId: CURRENT_USER_ID,
        answers,
        useLlm: true,
      });
      setResult(data);
      setGenerationProgress(completeProfileGenerationProgress(data));
      setSubmitState("done");
    } catch (err) {
      const message = err.data?.detail || err.data?.error || err.message || "提交失败";
      setError(message);
      setGenerationProgress(failProfileGenerationProgress(message));
      setSubmitState("error");
    }
  };

  return (
    <div className="page" data-screen-label="02 能力评估">
      <Breadcrumb items={[{ label: "工作台", to: "home" }, { label: "AI 交易能力评估" }]} onNav={onNav}/>

      <section className="sub-hero">
        <div>
          <div className="eyebrow"><span className="bar"></span>01 · ASSESSMENT ENGINE</div>
          <h1>把<span className="hl-inline">“我交易不稳定”</span><br/>变成可量化的能力画像。</h1>
          <p className="lede">
            通过 40 道交易能力画像题 + 历史交易记录导入，AI 交易能力评估引擎从 5 个维度评估你的交易能力，识别行为模式，给出当前训练阶段与下一步训练方向。
          </p>
          <div className="sub-hero-actions">
            <button className="btn btn-blue" onClick={startFullAssessment} disabled={loadState !== "ready"}>
              开始完整评估 · 40 题 <Icon.Arrow size={14}/>
            </button>
          </div>
          <div className="sub-hero-meta">
            <div className="sub-meta-item">
              <div className="l">维度</div>
              <div className="v">5 项 · 各 20 分</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">题目数</div>
              <div className="v">{questions.length || 40} 题完整画像</div>
            </div>
            <div className="sub-meta-item">
              <div className="l">输出</div>
              <div className="v">能力画像 + 训练路径</div>
            </div>
          </div>
        </div>

        <div className="radar-card">
          <div className="radar-card-head">
            <div>
              <div className="ttl">能力画像{hasProfile ? "结果" : "待生成"}</div>
              <div className="typ">{profileReport?.trader_type ?? "暂无能力画像"}</div>
            </div>
            <span className={`tag ${hasProfile ? "amber" : ""}`}>{hasProfile ? `总分 ${profileReport.total_score} / 100` : "完成评估后生成"}</span>
          </div>
          {hasProfile ? (
            <RadarChart dimensions={dimensions}/>
          ) : (
            <div className="radar-empty">
              <div className="radar-empty-title">等待完成评估</div>
              <p>提交完整问卷后，系统会生成 5 维度雷达图、总分、交易者类型和下一步训练路径。</p>
            </div>
          )}
          <div className="radar-dim-list">
            {dimensions.map((d) => (
              <div key={d.key} className="radar-dim">
                <span className="n">{d.name}</span>
                <span className="s mono">{hasProfile ? d.v : "--"}<span className="of">/20</span></span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-eyebrow">
          <span className="num mono">02</span>
          <h2>5 个评估维度，覆盖交易能力的完整光谱</h2>
        </div>
        <div className="dim-grid">
          {dimensions.map((d) => (
            <div key={d.key} className="dim-card">
              <div className="dc-num">{d.num}</div>
              <div className="dc-ttl">{d.name}</div>
              <div className="dc-desc">{d.desc}</div>
              <div className="dc-bar"><i style={{ width: `${hasProfile ? d.v * 5 : 0}%` }}/></div>
            </div>
          ))}
        </div>
      </section>

      <section className="section" ref={questionRef}>
        <div className="section-eyebrow">
          <span className="num mono">03</span>
          <h2>{started ? "完整画像问卷 · 40 题" : "后端问卷 · full_assessment"}</h2>
        </div>

        {loadState === "loading" && (
          <div className="q-status">正在加载问卷...</div>
        )}

        {loadState === "error" && (
          <div className="q-status error">
            <span>{error}</span>
            <button className="btn btn-blue" onClick={loadQuestionnaire}>重新加载</button>
          </div>
        )}

        {loadState === "ready" && currentQuestion && (
          <div className="q-preview">
            <div className="qp-left">
              <div className="qp-q mono">
                QUESTION {String(currentIndex + 1).padStart(2, "0")} / {String(questions.length).padStart(2, "0")}
              </div>
              {currentSection && <div className="q-section-tag">{currentSection.title}</div>}
              <p className="qp-text">{currentQuestion.text}</p>
              <textarea
                className="qa-textarea"
                rows="7"
                value={answersById[currentQuestion.id] ?? ""}
                onChange={(event) => updateAnswer(event.target.value)}
                placeholder="输入你的真实交易行为和判断依据..."
              />
              <div className="qp-progress">
                <span className="mono">{String(currentIndex + 1).padStart(2, "0")} / {String(questions.length).padStart(2, "0")}</span>
                <div className="bar"><i style={{ width: `${progressPct}%` }}/></div>
                <span>{answeredCount} 已填写</span>
              </div>
              <div className="qp-actions">
                <button className="btn btn-ghost" onClick={goPrev} disabled={currentIndex === 0 || submitState === "submitting"}>上一题</button>
                <button className="btn btn-blue" onClick={goNext} disabled={submitState === "submitting"}>
                  {currentIndex === questions.length - 1 ? (submitState === "submitting" ? "生成中..." : "生成评估结果") : "下一题"}
                </button>
              </div>
              {generationProgress.status !== "idle" && (
                <div className={`generation-progress ${generationProgress.status}`}>
                  <div className="gp-head">
                    <div>
                      <div className="gp-title">{generationProgress.title}</div>
                      <div className="gp-detail">{generationProgress.detail}</div>
                    </div>
                    <div className="gp-percent mono">{Math.round(generationProgress.percent)}%</div>
                  </div>
                  <div className="gp-bar"><i style={{ width: `${generationProgress.percent}%` }}/></div>
                  <div className="gp-steps">
                    {generationProgress.steps.map((step) => (
                      <span key={step.key} className={`gp-step ${step.status}`}>
                        {step.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {submitState === "done" && report && (
                <div className="qp-result">
                  <strong>完整评估已完成</strong>
                  <span>{report.profile_summary || report.summary}</span>
                </div>
              )}
              {submitState === "error" && (
                <div className="qp-result error">
                  <strong>提交失败</strong>
                  <span>{error}</span>
                </div>
              )}
            </div>

            <div className="qp-right">
              <h4>8 套问卷分组</h4>
              <div className="qa-section-list">
                {sectionStats.map((section) => (
                  <button
                    key={section.id}
                    className={`qa-section ${currentSection?.id === section.id ? "active" : ""}`}
                    onClick={() => jumpToQuestion(section.question_ids?.[0])}
                  >
                    <span>{section.title}</span>
                    <span className="mono">{section.done}/{section.total}</span>
                  </button>
                ))}
              </div>
              <div className="qa-mini-list">
                {(currentSection?.question_ids ?? questions.slice(currentIndex, currentIndex + 5).map((q) => q.id)).map((id) => {
                  const index = questions.findIndex((question) => question.id === id);
                  const question = questions[index];
                  if (!question) return null;
                  return (
                    <button
                      key={question.id}
                      className={`qa-mini ${index === currentIndex ? "active" : ""} ${(answersById[question.id] ?? "").trim() ? "done" : ""}`}
                      onClick={() => jumpToQuestion(question.id)}
                      aria-label={`Question ${String(index + 1).padStart(2, "0")} · ${question.id}`}
                    >
                      <span className="qpn">{String(index + 1).padStart(2, "0")}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-eyebrow">
          <span className="num mono">04</span>
          <h2>{report ? "评估结果" : "评估完成后你将获得"}</h2>
        </div>
        <div className="assessment-output-grid">
          <div className="card">
            <span className="tag blue">能力画像</span>
            <h3 style={{ marginTop: 14, fontSize: 17 }}>5 维度雷达图 + 总分</h3>
            <p style={{ fontSize: 13, color: "var(--ink-500)", lineHeight: 1.6, marginTop: 8, marginBottom: 0 }}>
              {report?.profile_summary || "完成评估后，系统会展示各维度强弱、总分和画像摘要。"}
            </p>
          </div>
          <div className="card">
            <span className="tag amber">交易者类型</span>
            <h3 style={{ marginTop: 14, fontSize: 17 }}>{profileReport?.trader_type ?? "所属阶段标签"}</h3>
            <p style={{ fontSize: 13, color: "var(--ink-500)", lineHeight: 1.6, marginTop: 8, marginBottom: 0 }}>
              {(profileReport?.risk_tags?.length ? profileReport.risk_tags.join(" / ") : "完成评估后，系统会根据当前阶段给出对应训练强度与约束规则。")}
            </p>
          </div>
          <div className="card">
            <span className="tag green">下一步训练</span>
            <h3 style={{ marginTop: 14, fontSize: 17 }}>个性化训练路径</h3>
            <p style={{ fontSize: 13, color: "var(--ink-500)", lineHeight: 1.6, marginTop: 8, marginBottom: 0 }}>
              {(report?.recommended_tasks?.length ? report.recommended_tasks.join("；") : "针对弱点推荐训练任务 —— 交易前计划训练、止损执行训练、复盘记录训练等。")}
            </p>
          </div>
        </div>
      </section>

      <Compliance/>
    </div>
  );
}

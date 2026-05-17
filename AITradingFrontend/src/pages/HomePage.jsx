import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import { Compliance } from "../components/Compliance.jsx";
import { getMemorySnapshot } from "../api/backend.js";
import { CURRENT_USER_ID } from "../userSession.js";

const PROFILE_DIMENSIONS = [
  { key: "market_understanding", l: "市场理解" },
  { key: "analysis_framework", l: "分析框架" },
  { key: "risk_control", l: "风险控制" },
  { key: "execution_discipline", l: "执行纪律" },
  { key: "review_ability", l: "复盘能力" },
];

function clampScore(value) {
  const score = Number(value ?? 0);
  return Math.max(0, Math.min(20, Number.isFinite(score) ? score : 0));
}

export function HomePage({ onNav }) {
  const [profile, setProfile] = useState(null);
  const [profileState, setProfileState] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    async function loadProfile() {
      setProfileState("loading");
      try {
        const memory = await getMemorySnapshot();
        if (cancelled) return;
        setProfile(memory.user_profiles?.[CURRENT_USER_ID] || null);
        setProfileState("ready");
      } catch {
        if (cancelled) return;
        setProfile(null);
        setProfileState("error");
      }
    }
    loadProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  const dims = useMemo(
    () => PROFILE_DIMENSIONS.map((dim) => {
      const score = clampScore(profile?.dimension_scores?.[dim.key]);
      return {
        ...dim,
        n: profile ? score : null,
        v: profile ? score * 5 : 0,
        t: score < 9 ? "danger" : score < 12 ? "warn" : "",
      };
    }),
    [profile],
  );
  const riskTags = profile?.risk_tags?.slice(0, 2) ?? [];

  return (
    <div className="page" data-screen-label="01 工作台">
      {/* HERO */}
      <section className="hero">
        <div className="hero-left">
          <div className="eyebrow">
            <span className="bar"></span>
            AI Trading Ability Training Workspace
          </div>
          <h1 className="h1" style={{ marginTop: 20 }}>
            从<span className="quote-mark">「</span>给答案<span className="quote-mark">」</span>
            <br />到<span className="hl">「给能力」</span>的系统性升级
          </h1>
          <p className="lede hero-lede">
            我们不提供“买什么”，而是训练你具备<strong style={{ color: "var(--ink-900)" }}>“如何决策与执行”</strong>的能力。
            <br />三大 AI 引擎，一套统一智能底座，把感觉问题变成可量化、可训练、可复盘的数据问题。
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={() => onNav("assessment")}>
              开始能力评估 <Icon.Arrow size={16} />
            </button>
          </div>
          <div className="hero-stats">
            <div className="hero-stat">
              <div className="v">5<span className="unit">个维度</span></div>
              <div className="l">能力评估</div>
            </div>
            <div className="hero-stat">
              <div className="v">10<span className="unit">类行为</span></div>
              <div className="l">错误归因</div>
            </div>
            <div className="hero-stat">
              <div className="v">6<span className="unit">个工具</span></div>
              <div className="l">MCP 调用链</div>
            </div>
          </div>
        </div>

        {/* HERO VISUAL: capability profile or new-user empty state */}
        <div className="hero-visual">
          <div className="hv-head">
            <span className="ttl">能力画像</span>
          </div>

          {profile ? (
            <div className="hv-score-block">
              <div className="num">{profile.total_score}<span className="of"> / 100</span></div>
              <div className="meta">
                <span className="lbl">{profile.trader_type}</span>
                <span className="delta">已生成画像</span>
              </div>
            </div>
          ) : (
            <div className="hv-empty">
              <div className="hv-empty-title">暂无能力画像</div>
              <p>
                {profileState === "error"
                  ? "暂时无法读取后端记忆，请稍后重试。"
                  : "完成能力评估后，这里会显示你的总分、交易者类型和 5 维度画像。"}
              </p>
              <button className="btn btn-blue" onClick={() => onNav("assessment")}>
                开始能力评估 <Icon.ArrowRight size={14}/>
              </button>
            </div>
          )}

          <div className="hv-bars">
            {dims.map((d) => (
              <div key={d.l} className="hv-bar-row">
                <span className="l">{d.l}</span>
                <span className={`t ${d.t || ""}`}><i style={{ width: `${d.v}%` }} /></span>
                <span className="v">{d.n == null ? "--" : d.n}/20</span>
              </div>
            ))}
          </div>

          <div className="hv-foot">
            <div className="tag-row">
              {profile ? (
                riskTags.length ? riskTags.map((tag) => <span className="tag amber" key={tag}>{tag}</span>) : <span className="tag green">画像已生成</span>
              ) : (
                <span className="tag">待评估</span>
              )}
            </div>
            <span>5 DIMENSIONS · {profile ? "LIVE" : "READY"}</span>
          </div>
        </div>
      </section>

      {/* ENTRY CARDS */}
      <section className="entries-section">
        <div className="section-head">
          <div>
            <div className="eyebrow"><span className="bar"></span>选择你的入口</div>
            <h2 className="h2" style={{ marginTop: 12 }}>三个明确任务入口，<br />对应你当前所处的训练阶段。</h2>
          </div>
          <p className="lede" style={{ maxWidth: 360, margin: 0 }}>
            后端是同一套智能底座：用户能力画像、交易记忆、研报检索、三大引擎、合规检查 —— 共享数据，分场景调用。
          </p>
        </div>

        <div className="entries">
          <button className="entry-card c-eval" onClick={() => onNav("assessment")}>
            <div className="ec-num">01 · ASSESSMENT</div>
            <div className="ec-icon"><Icon.Eval size={24} /></div>
            <h3>AI 交易能力评估</h3>
            <p className="ec-desc">
              通过题单与历史交易记录，识别你的行为模式与弱点，输出 5 维度能力画像与训练建议。
            </p>
            <ul className="ec-bullets">
              <li>8 道情境题 + 历史交易导入</li>
              <li>能力雷达图与交易者类型</li>
              <li>个性化训练方向推荐</li>
            </ul>
            <div className="ec-cta">
              <span>开始评估</span>
              <Icon.ArrowRight size={14} />
            </div>
          </button>

          <button className="entry-card c-train" onClick={() => onNav("training")}>
            <div className="ec-num">02 · TRAINING</div>
            <div className="ec-icon"><Icon.Train size={24} /></div>
            <h3>AI 行为训练</h3>
            <p className="ec-desc">
              交易前 / 持仓中检查你的交易计划完整度，生成行为约束任务，把投资知识转为可落地的执行动作。
            </p>
            <ul className="ec-bullets">
              <li>7 个交易场景模板</li>
              <li>计划完整度评分 + 风险标签</li>
              <li>训练任务自动写入下一笔</li>
            </ul>
            <div className="ec-cta">
              <span>进入训练</span>
              <Icon.ArrowRight size={14} />
            </div>
          </button>

          <button className="entry-card c-review" onClick={() => onNav("review")}>
            <div className="ec-num">03 · REVIEW</div>
            <div className="ec-icon"><Icon.Review size={24} /></div>
            <h3>AI 智能复盘</h3>
            <p className="ec-desc">
              复盘每一笔交易，分析错误归因与历史重复模式，沉淀为长期交易记忆，形成正向反馈闭环。
            </p>
            <ul className="ec-bullets">
              <li>10 类错误行为自动识别</li>
              <li>历史模式匹配 · 重复问题预警</li>
              <li>新规则写入长期记忆</li>
            </ul>
            <div className="ec-cta">
              <span>开始复盘</span>
              <Icon.ArrowRight size={14} />
            </div>
          </button>
        </div>

        {/* Smart input */}
        <div className="smart-input">
          <div className="si-icon"><Icon.Sparkle size={16} /></div>
          <input placeholder="你也可以直接描述交易问题，例如：我今天买入某股票，仓位 30%，最近三天涨得很强，想加仓但有点犹豫…" />
          <div className="si-hints">
            <span className="si-hint">↑ 自动判断入口</span>
          </div>
          <button className="btn btn-blue">
            智能分流 <Icon.ArrowRight size={14} />
          </button>
        </div>
      </section>

      {/* LOOP DIAGRAM */}
      <section className="loop-section">
        <div className="eyebrow">
          <span className="bar"></span>
          持续进化闭环
        </div>
        <h2 style={{ marginTop: 16 }}>不是一次回答，而是长期陪伴训练。</h2>
        <p className="lede">每一次交易、每一份复盘都成为下一次训练的输入。能力画像随时间持续更新，错误模式被识别并被规则化阻断。</p>

        <div className="loop-flow">
          <div className="loop-node">
            <div className="n-num">01</div>
            <div className="n-label">交易行为</div>
            <div className="n-desc">用户在真实市场中产生买入、卖出、加仓等操作</div>
          </div>
          <div className="loop-arrow"><Icon.ArrowFlow size={20} /></div>

          <div className="loop-node">
            <div className="n-num">02</div>
            <div className="n-label">数据记录</div>
            <div className="n-desc">交易计划、实际行为、当时情绪状态被结构化记录</div>
          </div>
          <div className="loop-arrow"><Icon.ArrowFlow size={20} /></div>

          <div className="loop-node">
            <div className="n-num">03</div>
            <div className="n-label">AI 智能分析</div>
            <div className="n-desc">三大引擎调用 MCP 工具，输出行为风险与错误归因</div>
          </div>
          <div className="loop-arrow"><Icon.ArrowFlow size={20} /></div>

          <div className="loop-node">
            <div className="n-num">04</div>
            <div className="n-label">针对性训练</div>
            <div className="n-desc">生成下一笔交易的行为约束任务，规则化阻断重复错误</div>
          </div>
          <div className="loop-arrow"><Icon.ArrowFlow size={20} /></div>

          <div className="loop-node">
            <div className="n-num">05</div>
            <div className="n-label">再次执行</div>
            <div className="n-desc">用户在新一轮交易中应用训练规则，闭环持续进化</div>
          </div>
        </div>
      </section>

      <Compliance />
    </div>
  );
}

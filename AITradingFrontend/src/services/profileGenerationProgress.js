export const PROFILE_GENERATION_STEPS = [
  { key: "questionnaire_load", label: "加载问卷定义", target: 12 },
  { key: "answer_validate", label: "校验 40 题答案", target: 24 },
  { key: "kimi_profile_generate", label: "生成用户画像", target: 68 },
  { key: "schema_validate", label: "校验画像格式", target: 78 },
  { key: "user_profile_update", label: "更新能力画像", target: 86 },
  { key: "compliance_guard_check", label: "合规检查", target: 93 },
  { key: "session_memory_write", label: "写入长期记忆", target: 98 },
];

export function idleProfileGenerationProgress() {
  return {
    status: "idle",
    percent: 0,
    activeIndex: 0,
    title: "等待生成",
    detail: "",
    steps: PROFILE_GENERATION_STEPS.map((step) => ({ ...step, status: "pending" })),
  };
}

export function startProfileGenerationProgress({ answerCount }) {
  return {
    status: "running",
    percent: 4,
    activeIndex: 0,
    title: "正在生成用户画像",
    detail: `已提交 ${answerCount} 条答案，正在进入画像生成管道。`,
    steps: PROFILE_GENERATION_STEPS.map((step, index) => ({
      ...step,
      status: index === 0 ? "active" : "pending",
    })),
  };
}

export function advanceProfileGenerationProgress(progress) {
  if (!progress || progress.status !== "running") return progress;
  const activeStep = PROFILE_GENERATION_STEPS[progress.activeIndex] ?? PROFILE_GENERATION_STEPS.at(-1);
  const nextPercent = Math.min(progress.percent + (activeStep.key === "kimi_profile_generate" ? 2 : 4), 96);
  let activeIndex = progress.activeIndex;

  if (nextPercent >= activeStep.target && activeIndex < PROFILE_GENERATION_STEPS.length - 1) {
    activeIndex += 1;
  }

  return {
    ...progress,
    percent: nextPercent,
    activeIndex,
    detail: detailForStep(PROFILE_GENERATION_STEPS[activeIndex]?.key),
    steps: PROFILE_GENERATION_STEPS.map((step, index) => ({
      ...step,
      status: index < activeIndex ? "done" : index === activeIndex ? "active" : "pending",
    })),
  };
}

export function completeProfileGenerationProgress(response) {
  const traceByName = new Map((response?.tool_trace ?? []).map((item) => [item.name, item]));
  return {
    status: "done",
    percent: 100,
    activeIndex: PROFILE_GENERATION_STEPS.length - 1,
    title: "用户画像已生成",
    detail: response?.report?.profile_summary || "画像、评分和训练建议已生成并写入记忆。",
    steps: PROFILE_GENERATION_STEPS.map((step) => ({
      ...step,
      status: traceByName.get(step.key)?.status === "fallback" ? "fallback" : "done",
    })),
  };
}

export function failProfileGenerationProgress(message) {
  return {
    status: "error",
    percent: 100,
    activeIndex: 0,
    title: "生成失败",
    detail: message || "画像生成管道返回错误。",
    steps: PROFILE_GENERATION_STEPS.map((step) => ({ ...step, status: "pending" })),
  };
}

function detailForStep(key) {
  switch (key) {
    case "questionnaire_load":
      return "读取 full_assessment 问卷定义。";
    case "answer_validate":
      return "检查 40 个 question_id 是否完整，空答案会保留。";
    case "kimi_profile_generate":
      return "调用 Kimi OpenAI-compatible 接口生成固定格式画像。";
    case "schema_validate":
      return "将模型输出规范化为 questionnaire_profile.v1。";
    case "user_profile_update":
      return "更新总分、交易者类型和 5 维度能力画像。";
    case "compliance_guard_check":
      return "检查报告内容并移除不合规表达。";
    case "session_memory_write":
      return "写入本次画像摘要和风险标签。";
    default:
      return "正在处理。";
  }
}

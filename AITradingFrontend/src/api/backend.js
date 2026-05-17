const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function readJson(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export async function getFullAssessment() {
  const res = await fetch(`${API_BASE}/api/questionnaires/full_assessment`);
  return readJson(res);
}

export async function getMemorySnapshot() {
  const res = await fetch(`${API_BASE}/api/memory`);
  return readJson(res);
}

export async function submitFullAssessment({ userId = "frontend_user", answers, useLlm = true }) {
  const res = await fetch(`${API_BASE}/api/questionnaires/full_assessment/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      use_llm: useLlm,
      answers,
    }),
  });
  return readJson(res);
}

export async function submitTrainingCheck({ userId = "frontend_user", scenario, message = "", tradePlan, useLlm = true }) {
  const res = await fetch(`${API_BASE}/api/training/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      scenario,
      message,
      trade_plan: tradePlan,
      use_llm: useLlm,
    }),
  });
  return readJson(res);
}

export async function getMarketKline({ symbol, market = "A", limit = 120, signal } = {}) {
  const params = new URLSearchParams({
    symbol: symbol ?? "",
    market,
    limit: String(limit),
  });
  const res = await fetch(`${API_BASE}/api/market/kline?${params.toString()}`, { signal });
  return readJson(res);
}

export async function submitReviewRun({ userId = "frontend_user", selfReflection = "", tradeRecord, useLlm = true }) {
  const res = await fetch(`${API_BASE}/api/review/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      use_llm: useLlm,
      self_reflection: selfReflection,
      trade_record: tradeRecord,
    }),
  });
  return readJson(res);
}

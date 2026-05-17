import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";

const chartMargins = { top: 18, right: 52, bottom: 28, left: 46 };

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toFixed(digits);
}

function formatAmount(value) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  if (number >= 100000000) return `${(number / 100000000).toFixed(1)}亿`;
  if (number >= 10000) return `${(number / 10000).toFixed(1)}万`;
  return String(Math.round(number));
}

function changeClass(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) return "flat";
  return number > 0 ? "up" : "down";
}

function optionalNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function sanitizeRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .map((row) => ({
      date: row.date,
      open: Number(row.open),
      close: Number(row.close),
      high: Number(row.high),
      low: Number(row.low),
      volume: optionalNumber(row.volume) ?? 0,
      amount: optionalNumber(row.amount),
      change_pct: optionalNumber(row.change_pct),
      turnover_rate: optionalNumber(row.turnover_rate),
    }))
    .filter((row) => row.date && [row.open, row.close, row.high, row.low].every(Number.isFinite));
}

function drawChart(svgElement, rows, colors) {
  const svg = d3.select(svgElement);
  svg.selectAll("*").remove();

  const bounds = svgElement.getBoundingClientRect();
  const width = Math.max(bounds.width || 720, 320);
  const height = Math.max(bounds.height || 340, 280);
  svg.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "股票日 K 线和成交量图");

  const innerWidth = width - chartMargins.left - chartMargins.right;
  const innerHeight = height - chartMargins.top - chartMargins.bottom;
  const priceHeight = Math.round(innerHeight * 0.72);
  const volumeTop = priceHeight + 22;
  const volumeHeight = Math.max(innerHeight - volumeTop, 48);
  const g = svg.append("g").attr("transform", `translate(${chartMargins.left},${chartMargins.top})`);

  const x = d3
    .scaleBand()
    .domain(rows.map((row) => row.date))
    .range([0, innerWidth])
    .paddingInner(0.28)
    .paddingOuter(0.12);

  const priceExtent = d3.extent(rows.flatMap((row) => [row.low, row.high]));
  const pricePadding = Math.max((priceExtent[1] - priceExtent[0]) * 0.08, 0.01);
  const y = d3
    .scaleLinear()
    .domain([priceExtent[0] - pricePadding, priceExtent[1] + pricePadding])
    .nice()
    .range([priceHeight, 0]);

  const volumeMax = d3.max(rows, (row) => row.volume) || 1;
  const yVolume = d3.scaleLinear().domain([0, volumeMax]).range([volumeHeight, 0]).nice();
  const tickDates = rows
    .filter((_, index) => index % Math.max(1, Math.ceil(rows.length / 5)) === 0)
    .map((row) => row.date);

  g.append("g")
    .attr("class", "kline-grid")
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerWidth).tickFormat(""))
    .call((selection) => selection.select(".domain").remove());

  g.append("g")
    .attr("class", "kline-axis kline-axis-price")
    .attr("transform", `translate(${innerWidth},0)`)
    .call(d3.axisRight(y).ticks(4).tickFormat((value) => formatNumber(value, 2)))
    .call((selection) => selection.select(".domain").remove());

  g.append("g")
    .attr("class", "kline-axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).tickValues(tickDates).tickFormat((value) => String(value).slice(5)))
    .call((selection) => selection.select(".domain").remove());

  const candle = g.append("g").selectAll("g").data(rows).join("g");
  candle
    .append("line")
    .attr("x1", (row) => (x(row.date) ?? 0) + x.bandwidth() / 2)
    .attr("x2", (row) => (x(row.date) ?? 0) + x.bandwidth() / 2)
    .attr("y1", (row) => y(row.high))
    .attr("y2", (row) => y(row.low))
    .attr("stroke", (row) => (row.close >= row.open ? colors.up : colors.down))
    .attr("stroke-width", 1);

  candle
    .append("rect")
    .attr("x", (row) => x(row.date) ?? 0)
    .attr("y", (row) => y(Math.max(row.open, row.close)))
    .attr("width", Math.max(x.bandwidth(), 2))
    .attr("height", (row) => Math.max(Math.abs(y(row.open) - y(row.close)), 1.5))
    .attr("rx", 1)
    .attr("fill", (row) => (row.close >= row.open ? colors.up : colors.down));

  g.append("g")
    .selectAll("rect")
    .data(rows)
    .join("rect")
    .attr("x", (row) => x(row.date) ?? 0)
    .attr("y", (row) => volumeTop + yVolume(row.volume))
    .attr("width", Math.max(x.bandwidth(), 2))
    .attr("height", (row) => volumeHeight - yVolume(row.volume))
    .attr("fill", (row) => (row.close >= row.open ? colors.upSoft : colors.downSoft));

  g.append("text")
    .attr("class", "kline-volume-label")
    .attr("x", 0)
    .attr("y", volumeTop - 8)
    .text("成交量");
}

export function KLineChart({ status = "idle", payload = null, error = "" }) {
  const svgRef = useRef(null);
  const rows = useMemo(() => sanitizeRows(payload?.kline), [payload]);
  const quote = payload?.quote || {};
  const technical = payload?.technical || {};
  const latest = rows[rows.length - 1];
  const displayName = quote.name || quote.symbol || payload?.symbol || "";

  useEffect(() => {
    if (status !== "ready" || !payload?.available || rows.length === 0 || !svgRef.current) return undefined;
    const root = getComputedStyle(document.documentElement);
    const colors = {
      up: root.getPropertyValue("--danger").trim() || "#dc2626",
      down: root.getPropertyValue("--success").trim() || "#16a34a",
      upSoft: "rgba(220, 38, 38, 0.25)",
      downSoft: "rgba(22, 163, 74, 0.24)",
    };
    const draw = () => {
      if (svgRef.current) {
        drawChart(svgRef.current, rows, colors);
      }
    };
    draw();
    const parent = svgRef.current.parentElement;
    if (!parent) return undefined;
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", draw);
      return () => window.removeEventListener("resize", draw);
    }
    const observer = new ResizeObserver(draw);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [payload, rows, status]);

  return (
    <section className="kline-panel" aria-label="公开行情背景">
      <div className="kline-head">
        <div>
          <div className="kline-eyebrow">PUBLIC MARKET CONTEXT</div>
          <h3>公开行情背景</h3>
        </div>
        <div className="kline-source">{payload?.source || "MarketDataProvider"}</div>
      </div>

      {status === "idle" && (
        <div className="kline-empty">输入 6 位 A 股代码后展示 K 线背景。</div>
      )}
      {status === "loading" && (
        <div className="kline-empty">正在加载公开行情背景...</div>
      )}
      {status === "error" && (
        <div className="kline-empty warn">{error || "行情背景暂不可用。"}</div>
      )}
      {status === "ready" && !payload?.available && (
        <div className="kline-empty warn">{payload?.errors?.[0] || "行情背景暂不可用。"}</div>
      )}

      {status === "ready" && payload?.available && (
        <>
          <div className="kline-summary">
            <div>
              <span>标的</span>
              <strong>{displayName || "--"}</strong>
            </div>
            <div>
              <span>最新</span>
              <strong>{formatNumber(quote.price ?? latest?.close)}</strong>
            </div>
            <div className={changeClass(quote.change_pct ?? latest?.change_pct)}>
              <span>涨跌幅</span>
              <strong>{formatNumber(quote.change_pct ?? latest?.change_pct)}%</strong>
            </div>
            <div>
              <span>成交额</span>
              <strong>{formatAmount(quote.amount ?? latest?.amount)}</strong>
            </div>
          </div>

          <div className="kline-chart-frame">
            <svg ref={svgRef}></svg>
          </div>

          <div className="kline-metrics">
            <span>3日 {formatNumber(technical.change_pct_3d)}%</span>
            <span>5日 {formatNumber(technical.change_pct_5d)}%</span>
            <span>20日 {formatNumber(technical.change_pct_20d)}%</span>
            <span>波动 {formatNumber(technical.volatility_20d)}</span>
          </div>
          <div className="kline-note">{payload?.compliance_note}</div>
        </>
      )}
    </section>
  );
}

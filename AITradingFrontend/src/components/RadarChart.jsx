// 5-dimension capability radar. Black stroke + 8% black fill — flat system,
// no gradients/shadows. Values are 0-20 per dimension.
export function RadarChart({ dimensions }) {
  const dims = dimensions ?? [
    { name: "市场理解", v: 12 },
    { name: "分析框架", v: 13 },
    { name: "风险控制", v: 10 },
    { name: "执行纪律", v: 8 },
    { name: "复盘能力", v: 14 },
  ];
  const size = 360;
  const cx = size / 2;
  const cy = size / 2;
  const r = 130;
  const n = dims.length;
  const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2;

  const ringPath = (factor) => dims.map((_, i) => {
    const a = angle(i);
    const x = cx + Math.cos(a) * r * factor;
    const y = cy + Math.sin(a) * r * factor;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ") + " Z";

  const valuePath = dims.map((d, i) => {
    const a = angle(i);
    const f = d.v / 20;
    const x = cx + Math.cos(a) * r * f;
    const y = cy + Math.sin(a) * r * f;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ") + " Z";

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="radar-svg">
      {[0.25, 0.5, 0.75, 1].map((f, i) => (
        <path key={i} d={ringPath(f)} fill="none" stroke="#E5E5E5" strokeWidth="1"/>
      ))}
      {dims.map((_, i) => {
        const a = angle(i);
        return (
          <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * r} y2={cy + Math.sin(a) * r} stroke="#E5E5E5" strokeWidth="1"/>
        );
      })}
      <path d={valuePath} fill="rgba(10, 10, 10, 0.08)" stroke="#0A0A0A" strokeWidth="1.5" strokeLinejoin="round"/>
      {dims.map((d, i) => {
        const a = angle(i);
        const f = d.v / 20;
        const x = cx + Math.cos(a) * r * f;
        const y = cy + Math.sin(a) * r * f;
        return <circle key={i} cx={x} cy={y} r="3.5" fill="#0A0A0A" stroke="#fff" strokeWidth="2"/>;
      })}
      {dims.map((d, i) => {
        const a = angle(i);
        const lr = r + 24;
        const x = cx + Math.cos(a) * lr;
        const y = cy + Math.sin(a) * lr;
        return (
          <text key={i} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="#525252" fontWeight="500" fontFamily="Tahoma, sans-serif">
            {d.name}
          </text>
        );
      })}
    </svg>
  );
}

// Sticky top navigation. Receives the active page key + a nav callback so
// active state and routing stay in lockstep with the router (see App.jsx).
export function Nav({ page, onNav }) {
  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="brand">
          <div className="brand-mark">AT</div>
          AI 交易能力训练工作台
          <span className="brand-sub">v1.0 · Hackathon</span>
        </div>
        <div className="nav-links">
          <button className={`nav-link ${page === "home" ? "active" : ""}`} onClick={() => onNav("home")}>工作台</button>
          <button className={`nav-link ${page === "assessment" ? "active" : ""}`} onClick={() => onNav("assessment")}>能力评估</button>
          <button className={`nav-link ${page === "training" ? "active" : ""}`} onClick={() => onNav("training")}>行为训练</button>
          <button className={`nav-link ${page === "review" ? "active" : ""}`} onClick={() => onNav("review")}>智能复盘</button>
        </div>
      </div>
    </nav>
  );
}

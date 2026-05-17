import { Icon } from "./Icon.jsx";

// Page-level compliance notice — investor-education positioning, no advice.
export function Compliance() {
  return (
    <div className="compliance">
      <div className="ico"><Icon.Shield size={18}/></div>
      <div>
        <strong>合规提示</strong> · 本系统仅用于<strong>投资教育</strong>与<strong>交易能力训练</strong>，不构成任何投资建议、个股推荐或买卖信号。系统不会输出“可以买 / 建议买入 / 目标价 / 止损价”等具体决策指令，仅评估你的交易计划完整度与行为风险。
      </div>
    </div>
  );
}

import { Link } from "react-router-dom";

export function SavingsPage() {
  return (
    <section>
      <p><Link to="/teams">返回</Link></p>
      <h1>节省回执怎么算</h1>
      <p>公式 <span className="mono">savings-receipt-v1</span>。同一次会审的实际用量，对照「这些优化如果没生效」的基线。基线不再调用模型，页面上也不给节省比例。</p>
      <article className="card">
        <h2>恒等式</h2>
        <pre>{`saved_tokens = baseline_tokens - actual_tokens = 三条杠杆的 token 之和
saved_cost   = baseline_cost   - actual_cost   = 三条杠杆的费用之和`}</pre>
        <p>没填单价时费用为 0，token 仍然可核对。优化没有生效时，节省为 0。</p>
      </article>
      <article className="card">
        <h2>三条杠杆</h2>
        <p><strong>共享前缀</strong>：专家调用上，供应商回报的缓存 token。回报 0 就是 0，即使提示词已经对齐。供应商不按段落拆开，所以不再按安全护栏的长度切分。</p>
        <p><strong>跳过未分配专家</strong>：协调者没分派的专家，按「仍然空跑一次」计算提示 token。不估计那次没有发生的补全。</p>
        <p><strong>缓存命中</strong>：本地响应缓存，以及协调者、复核人的供应商缓存。本地命中的实际费用按 0。</p>
        <p>供应商把缓存算进 prompt tokens 时，token 节省可以是 0，费用仍按未缓存单价对比。</p>
      </article>
      <article className="card">
        <h2>不算节省</h2>
        <p>Token 预算超限而跳过的角色会列出来，不进入杠杆。协调者没跑完时，不估计还没分派的专家。</p>
        <p className="hint">仓库里的完整说明是 docs/SAVINGS.md。离线脚本 scripts/token_savings_report.py 用同一公式，但是演示数据，不是某次线上运行的回执。</p>
      </article>
    </section>
  );
}

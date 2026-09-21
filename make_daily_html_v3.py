# -*- coding: utf-8 -*-
"""v3 预测网页渲染：排名榜 + 每只股票概率/评级/理由/事件 + 回测说明 + 免责声明。
输出 self-contained HTML（内嵌 CSS，无需外部依赖）。
"""
import html as _h

import pandas as pd

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>首板连板预测 · v3 重建版 · {date}</title>
<style>
  body {{ font-family: "Microsoft YaHei", -apple-system, sans-serif; margin: 0; background: #f5f6fa; color: #222; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 16px; }}
  h1 {{ font-size: 22px; margin: 8px 0 2px; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 14px; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card .k {{ color: #888; font-size: 12px; }}
  .card .v {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
  .v.red {{ color: #d23a2e; }} .v.green {{ color: #0b7a3b; }}
  .panel {{ background: #fff; border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .panel h2 {{ font-size: 16px; margin: 0 0 10px; border-left: 4px solid #d23a2e; padding-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 6px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafbfc; position: sticky; top: 0; font-size: 12px; color: #555; }}
  tr:hover td {{ background: #f8f9fb; }}
  .rank {{ font-weight: 700; color: #d23a2e; width: 36px; }}
  .prob {{ font-weight: 700; }}
  .bar {{ display: inline-block; height: 10px; border-radius: 5px; vertical-align: middle; margin-right: 6px; }}
  .tag {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; background: #fff1e8; color: #c2410c; }}
  .tag.ev {{ background: #e6f4ea; color: #0b7a3b; }}
  .reason {{ color: #555; font-size: 12px; line-height: 1.5; }}
  .note {{ color: #999; font-size: 12px; margin-top: 8px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .pill {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:700; }}
  .pA {{ background:#0b7a3b; color:#fff; }} .pB {{ background:#1a7fd1; color:#fff; }}
  .pC {{ background:#e6a23c; color:#fff; }} .pD {{ background:#aaa; color:#fff; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>首板连板预测 · v3 多维评分系统</h1>
  <div class="sub">{date} 涨停池 → 预测 {next_day} 连板（尾盘买入口径）· 六因子加权 + 分身位分位校准 + 消息面事件识别</div>

  <div class="cards">
    <div class="card"><div class="k">当日涨停</div><div class="v red">{total_lim}</div></div>
    <div class="card"><div class="k">候选池</div><div class="v">{pool_n}</div></div>
    <div class="card"><div class="k">最高分</div><div class="v">{top_score}</div></div>
    <div class="card"><div class="k">最高概率</div><div class="v green">{top_prob}</div></div>
    <div class="card"><div class="k">模型版本</div><div class="v">v3</div></div>
  </div>

  {table_html}

  <div class="panel">
    <h2>v3 模型说明（请先阅读）</h2>
    <div class="grid2">
      <div>
        <b>六因子加权（权重由一年回测网格搜索得出）</b>
        <ul>
          <li>连板身位 30% · 涨停频率 20% · 5日动量 15%</li>
          <li>换手率 15%（低换手=惜售，回测晋级率显著更高）</li>
          <li>放量倍数 10% · 市场情绪 10%</li>
        </ul>
        <b>概率 = 分身位（1/2/3/4+板）× 综合分分位校准</b>
        <div class="note">不再按旧公式线性压扁概率；每只股票的概率 = 同身位池内历史同分位实测晋级率（近一年 27,439 个涨停样本回测），同身位股票概率不再趋同。</div>
      </div>
      <div>
        <b>回测命中率（2025-06-02 ~ 2026-09-18，训练/验证 5:5 切分）</b>
        <table>
          <tr><th>策略</th><th>全期</th><th>训练段</th><th>验证段</th></tr>
          <tr><td>全池 TOP1</td><td><b>57.05%</b></td><td>57.78%</td><td>56.12%</td></tr>
          <tr><td>低位池(1-3板) TOP1</td><td><b>56.74%</b></td><td>61.11%</td><td>51.08%</td></tr>
          <tr><td>首板池 TOP1</td><td><b>35.42%</b></td><td>41.11%</td><td>28.06%</td></tr>
          <tr><td>全池 TOP5</td><td>49.97%</td><td>53.78%</td><td>45.04%</td></tr>
        </table>
        <div class="note">v2 → v3：全池 TOP1 49.53% → 57.05%；首板池 TOP1 25.08% → 35.42%（提升 10 个百分点）。首板晋级二板受信息极限约束（首板次日晋级率仅 16%），50%+ 需叠加当日盘口（封板时间/封单金额，本模型已纳入展示，暂未回测）。</div>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>数据与验证</h2>
    <ul>
      <li>数据源：baostock 全市场日线（1,838,821 行 / 6,185 只，含换手率/成交额/成交量）+ 东方财富涨停池（封板时间/封板资金/炸板/换手率）+ 个股新闻（消息面事件）。</li>
      <li>口径：当日涨停 → 次日收盘仍涨停 = 命中（连板晋级）；尾盘买入假设。ST/退市/新股按实际涨跌幅阈值区分。</li>
      <li>复现：<code>python v3_backtest.py bs_daily_v3.csv</code>；权重搜索 <code>python explore_v3_factors.py bs_daily_v3.csv</code>。</li>
      <li>事件识别：重组/收购/业绩预增/中标/增持/AI 等关键词命中当日新闻标题 → 综合分加成（标注"消息面"，未回测部分已注明）。</li>
    </ul>
    <div class="note">免责声明：本模型基于历史统计规律，不构成投资建议。连板为高风险博弈，请独立判断、控制仓位。</div>
  </div>
</div>
</body>
</html>
"""


def _prob_bar(p: float) -> str:
    pct = min(100, max(0, p * 100))
    color = "#0b7a3b" if p >= 0.4 else ("#1a7fd1" if p >= 0.3 else "#e6a23c" if p >= 0.2 else "#bbb")
    return (f'<span class="bar" style="width:{int(pct)}px;background:{color}"></span>'
            f'<span class="prob">{pct:.1f}%</span>')


def _grade(p: float) -> str:
    if p >= 0.50: return '<span class="pill pA">A+</span>'
    if p >= 0.40: return '<span class="pill pA">A</span>'
    if p >= 0.30: return '<span class="pill pB">B</span>'
    if p >= 0.20: return '<span class="pill pC">C</span>'
    return '<span class="pill pD">D</span>'


def make_daily_html_v3(scored: pd.DataFrame, date: str, next_day: str,
                       total_limit_up: int, out_path: str = None) -> str:
    df = scored.copy()
    if out_path is None:
        out_path = f"daily_prediction_v3_{date.replace('-', '')}.html"

    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        ev = ""
        if r.get("事件标签"):
            ev = f'<span class="tag ev">{_h.escape(str(r["事件标签"]))}</span>'
        reason = _h.escape(str(r.get("预测理由", "")))
        theme = _h.escape(str(r.get("所属行业", "")))
        prob = float(r.get("次日连板概率", 0))
        board = int(r.get("连板数", 1))
        rows.append(
            f"<tr><td class='rank'>{i}</td>"
            f"<td><b>{_h.escape(str(r['名称']))}</b><br><span class='note'>{_h.escape(str(r['代码']))} · {theme} · {board}板</span></td>"
            f"<td>{_prob_bar(prob)}<br>{_grade(prob)}</td>"
            f"<td>{_h.escape(str(r.get('综合分', '')))}</td>"
            f"<td>{ev}<div class='reason'>{reason}</div></td></tr>")
    table_html = f"""
    <div class="panel">
      <h2>预测排名（按综合分降序）</h2>
      <table>
        <tr><th>#</th><th>股票</th><th>次日连板概率</th><th>综合分</th><th>预测理由</th></tr>
        {''.join(rows)}
      </table>
    </div>"""

    top_score = df["综合分"].max() if len(df) else 0
    top_prob = df["次日连板概率"].max() if len(df) else 0
    html = TEMPLATE.format(
        date=date, next_day=next_day, total_lim=total_limit_up,
        pool_n=len(df), top_score=top_score,
        top_prob=f"{float(top_prob)*100:.1f}%", table_html=table_html)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path

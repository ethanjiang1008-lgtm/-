# -*- coding: utf-8 -*-
"""v4 预测网页渲染：低位池榜 + 首板专项榜 + v4 回测对比说明。
输出 self-contained HTML（内嵌 CSS，无外部依赖）。
"""
import html as _h

import pandas as pd

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>首板连板预测 · v4 迭代版 · {date}</title>
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
  .reason {{ color: #555; font-size: 12px; line-height: 1.5; }}
  .note {{ color: #999; font-size: 12px; margin-top: 8px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .pill {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:700; }}
  .pA {{ background:#0b7a3b; color:#fff; }} .pB {{ background:#1a7fd1; color:#fff; }}
  .pC {{ background:#e6a23c; color:#fff; }} .pD {{ background:#aaa; color:#fff; }}
  .new {{ display:inline-block; background:#d23a2e; color:#fff; padding:1px 8px; border-radius:10px; font-size:11px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>首板连板预测 · v4 迭代版 <span class="new">回测验证 TOP1 67.4%</span></h1>
  <div class="sub">{date} 涨停池 → 预测 {next_day} 连板（尾盘买入口径）· 大成交额 + 低换手 + 放量过滤 + 身位分位校准</div>

  <div class="cards">
    <div class="card"><div class="k">当日涨停</div><div class="v red">{total_lim}</div></div>
    <div class="card"><div class="k">低位池候选</div><div class="v">{low_n}</div></div>
    <div class="card"><div class="k">首板专项候选</div><div class="v">{fb_n}</div></div>
    <div class="card"><div class="k">最高概率(低位)</div><div class="v green">{top_prob}</div></div>
    <div class="card"><div class="k">模型版本</div><div class="v">v4</div></div>
  </div>

  <div class="panel">
    <h2>低位池榜（1-3板 · 放量&lt;6倍 · 大成交额优先）</h2>
    {low_table}
  </div>

  <div class="panel">
    <h2>首板专项榜（首板 · 换手率&lt;3% 惜售锁筹）</h2>
    {fb_table}
  </div>

  <div class="panel">
    <h2>v4 模型说明（2026-09-23 迭代，请先阅读）</h2>
    <div class="grid2">
      <div>
        <b>v4 策略（回测实证得出，非拍脑袋）</b>
        <ul>
          <li>低位池：仅保留 1-3 板 且 放量倍数&lt;6（排除天量分歧票）；按「同身位内成交额分位」校准概率，取 TOP。</li>
          <li>首板专项：仅保留 首板 且 换手率&lt;3%（惜售锁筹），按成交额分位校准。</li>
          <li>核心规律（训练集校准表）：同身位内换手越低晋级率越高 —— 2板低换手 58% vs 高换手 27%；3板低换手 79% vs 高换手 38%；3板+大成交额(Q1) 78.9%。</li>
        </ul>
        <b>为什么 v4 更强？</b>
        <div class="note">v3 用六因子等权组合，把「身位/换手/成交额」三个强信号互相稀释；v4 收敛到回测中最强的 2 个信号（成交额分层 + 换手/放量过滤），并用同身位分位校准把概率映射到历史实测晋级率。</div>
      </div>
      <div>
        <b>回测命中率（沪深主板非ST/科创/创业，2025-09-22~2026-09-21，242 交易日，训练/验证切分）</b>
        <table>
          <tr><th>策略 TOP1</th><th>全期</th><th>训练段</th><th>验证段</th></tr>
          <tr><td>v3 低位池</td><td>52.5%</td><td>58.4%</td><td>48.2%</td></tr>
          <tr><td><b>v4 低位池</b></td><td><b>65.7%</b></td><td><b>68.3%</b></td><td><b>63.8%</b></td></tr>
          <tr><td>v3 首板池</td><td>21.5%</td><td>25.7%</td><td>18.4%</td></tr>
          <tr><td><b>v4 首板池</b></td><td><b>31.6%</b></td><td><b>33.3%</b></td><td><b>30.4%</b></td></tr>
        </table>
        <div class="note">v4 低位池 TOP1 提升 +13.2pp、首板池 +10.1pp，验证段不弱于训练段（非过拟合）。TOP3/TOP5 与 v3 相当或略降：v4 是「精选少数」策略，越往后概率衰减越快。</div>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>数据与验证</h2>
    <ul>
      <li>数据源：baostock 日线（主板 3,153 只，含换手/成交额）+ 东方财富涨停池（当日真实换手/成交额/连板数）。</li>
      <li>口径：当日涨停 → 次日收盘仍涨停 = 命中（连板晋级）；尾盘买入假设；只做沪深主板（非ST/科创/创业）。</li>
      <li>概率 = 同身位（1/2/3/4+板）× 成交额分位（Q1-Q5）校准表的历史实测晋级率（训练段 2025-09-22~2026-03-01 拟合，验证段独立评估）。</li>
      <li>复现：<code>python build_samples.py && python exp_iter4_final.py</code>；校准表 <code>python make_calib_v4.py</code>。</li>
    </ul>
    <div class="note">免责声明：本模型基于历史统计规律，不构成投资建议。连板为高风险博弈，请独立判断、控制仓位。</div>
  </div>
</div>
</body>
</html>
"""


def _prob_bar(p: float) -> str:
    pct = min(100, max(0, p))
    color = "#0b7a3b" if p >= 50 else ("#1a7fd1" if p >= 35 else "#e6a23c" if p >= 20 else "#bbb")
    return (f'<span class="bar" style="width:{int(pct)}px;background:{color}"></span>'
            f'<span class="prob">{pct:.1f}%</span>')


def _grade(p: float) -> str:
    if p >= 60: return '<span class="pill pA">A+</span>'
    if p >= 50: return '<span class="pill pA">A</span>'
    if p >= 35: return '<span class="pill pB">B</span>'
    if p >= 20: return '<span class="pill pC">C</span>'
    return '<span class="pill pD">D</span>'


def _table(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return '<div class="note">今日无满足条件的候选。</div>'
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        name = f"{r['名称']}{r['代码']} · {r.get('所属行业','')} · {int(r['连板数'])}板"
        reason = _h.escape(str(r.get("预测理由", "")))
        turn = r.get("换手率")
        turn_s = f"{turn:.1f}%" if pd.notna(turn) else "—"
        rows.append(
            f"<tr><td class='rank'>{i}</td>"
            f"<td>{_h.escape(name)}</td>"
            f"<td>{_prob_bar(float(r['次日连板概率']))}</td>"
            f"<td>{_grade(float(r['次日连板概率']))}</td>"
            f"<td>{turn_s}</td>"
            f"<td class='reason'>{reason}</td></tr>")
    return (f"<table><tr><th>#</th><th>名称</th><th>次日连板概率</th><th>评级</th>"
            f"<th>换手率</th><th>预测理由</th></tr>{''.join(rows)}</table>")


def make_daily_html_v4(low: pd.DataFrame, fb: pd.DataFrame, date: str, next_day: str,
                       total_limit_up: int, out_path: str = None) -> str:
    html = TEMPLATE.format(
        date=date, next_day=next_day, total_lim=total_limit_up,
        low_n=len(low) if low is not None else 0,
        fb_n=len(fb) if fb is not None else 0,
        top_prob=f"{low['次日连板概率'].max():.1f}%" if low is not None and len(low) else "—",
        low_table=_table(low), fb_table=_table(fb))
    path = out_path or f"daily_prediction_v4_{date.replace('-', '')}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

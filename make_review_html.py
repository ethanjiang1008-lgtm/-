# -*- coding: utf-8 -*-
"""生成 2026-09-21 → 09-22 复盘网页。"""
import pandas as pd

df = pd.read_csv("review_0922_detail.csv", dtype={"code": str})
df["code"] = df["code"].str.zfill(6)

total = len(df)
hits = int(df["hit"].sum())
hit_rate = hits / total * 100

def top(n):
    t = df.head(n)
    h = int(t["hit"].sum())
    return h, len(t), h / len(t) * 100

def rows_html(sub):
    out = []
    for _, r in sub.iterrows():
        cls = "ok" if r["hit"] else "no"
        mark = "✓ 晋级" if r["hit"] else "— 未涨停"
        reason = str(r["reason"])[:110]
        ev = f"<span class='tag ev'>{r['event']}</span>" if str(r["event"]) != "nan" and r["event"] else ""
        out.append(
            f"<tr class='{cls}'><td>{r['rank']}</td><td><b>{r['name']}</b><br>"
            f"<span class='note'>{r['code']} · {r['industry']} · {r['boards']}板</span></td>"
            f"<td>{r['prob']*100:.1f}%</td><td>{r['score']}</td>"
            f"<td>{ev}<div class='reason'>{reason}</div></td>"
            f"<td>{mark}</td></tr>")
    return "\n".join(out)

h1, t1, r1 = top(1)
h3, t3, r3 = top(3)
h5, t5, r5 = top(5)
h10, t10, r10 = top(10)
h20, t20, r20 = top(20)

# 分身位
b_rows = ""
for b, g in df.groupby("boards"):
    h = int(g["hit"].sum())
    base = {1: "16.4%", 2: "29.6%", 3: "43.1%"}.get(b, "—")
    b_rows += f"<tr><td>{b}板</td><td>{len(g)}</td><td class='{(('ok' if h/len(g)>=0.2 else 'no'))}'>{h}/{len(g)} = {h/len(g)*100:.1f}%</td><td>回测基准 {base}</td></tr>"

# 校准档
cal_rows = ""
for lo, hi, label in [(0.50, 1.0, "≥50% (A+强预期)"), (0.30, 0.50, "30-50% (B)"),
                      (0.20, 0.30, "20-30% (C)"), (0.0, 0.20, "<20% (D)")]:
    g = df[(df["prob"] >= lo) & (df["prob"] < hi)]
    if len(g) == 0:
        continue
    h = int(g["hit"].sum())
    act = h / len(g) * 100
    pred = g["prob"].mean() * 100
    diff = act - pred
    cls = "ok" if abs(diff) < 8 else ("down" if diff < 0 else "up")
    cal_rows += f"<tr><td>{label}</td><td>{len(g)}</td><td>{pred:.1f}%</td><td class='{cls}'>{act:.1f}%</td><td>{diff:+.1f}pp</td></tr>"

hit_df = df[df["hit"]]
hit_rows = rows_html(hit_df)

watch_codes = ["000504", "002453", "600630", "600448", "601579", "601811",
               "600825", "600301", "000532"]
watch = df[df["code"].isin(watch_codes)].sort_values("rank")
watch_rows = rows_html(watch)

css = """body{font-family:"Microsoft YaHei",sans-serif;margin:0;background:#f5f6fa;color:#222}
.wrap{max-width:1080px;margin:0 auto;padding:18px}
h1{font-size:22px}
.sub{color:#666;font-size:13px;margin-bottom:16px}
.panel{background:#fff;border-radius:10px;padding:14px 18px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.panel h2{font-size:16px;margin:0 0 10px;border-left:4px solid #d23a2e;padding-left:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 8px;text-align:left;border-bottom:1px solid #eee;vertical-align:top}
th{background:#fafbfc}
.up{color:#0b7a3b;font-weight:700}
.down{color:#d23a2e;font-weight:700}
.no .reason{color:#999}
.ok td:first-child{font-weight:700}
.note{color:#999;font-size:11px}
.reason{color:#666;font-size:12px;margin-top:3px}
.tag{display:inline-block;font-size:11px;padding:1px 8px;border-radius:10px;background:#f0f7ff;color:#1a7fd1;margin-bottom:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}
.card{background:#fff;border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center}
.card .num{font-size:26px;font-weight:700;color:#d23a2e}
.card .num.g{color:#0b7a3b}
.card .lbl{color:#888;font-size:12px;margin-top:2px}
.note2{color:#888;font-size:12px}"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>预测复盘 · 09-21 → 09-22</title><style>{css}</style></head><body><div class="wrap">
<h1>预测复盘：2026-09-21 榜单 → 09-22 实际表现</h1>
<div class="sub">口径：昨日收盘后预测（尾盘买入）→ 今日收盘仍涨停 = 命中（与回测一致）· 今日全市场涨停 {63} 只 · 数据源：东方财富涨停池</div>

<div class="cards">
  <div class="card"><div class="num">{total}</div><div class="lbl">昨日预测(1-3板池)</div></div>
  <div class="card"><div class="num g">{hits}</div><div class="lbl">今日晋级涨停</div></div>
  <div class="card"><div class="num g">{hit_rate:.1f}%</div><div class="lbl">总命中率</div></div>
  <div class="card"><div class="num g">{"✓" if h1 else "✗"}</div><div class="lbl">TOP1 命中 ({r1:.0f}%)</div></div>
  <div class="card"><div class="num">{r3:.0f}%</div><div class="lbl">TOP3 ({h3}/{t3})</div></div>
  <div class="card"><div class="num">{r10:.0f}%</div><div class="lbl">TOP10 ({h10}/{t10})</div></div>
  <div class="card"><div class="num">{r20:.0f}%</div><div class="lbl">TOP20 ({h20}/{t20})</div></div>
</div>

<div class="panel"><h2>① 分位段命中（TOP 区间）</h2>
<table><tr><th>区间</th><th>命中</th><th>命中率</th></tr>
<tr><td>TOP1（南华生物 55.9%）</td><td>{h1}/{t1}</td><td class="up">{r1:.0f}%</td></tr>
<tr><td>TOP3</td><td>{h3}/{t3}</td><td class="{('up' if r3>=50 else 'down')}">{r3:.1f}%</td></tr>
<tr><td>TOP5</td><td>{h5}/{t5}</td><td class="{('up' if r5>=50 else 'down')}">{r5:.1f}%</td></tr>
<tr><td>TOP10</td><td>{h10}/{t10}</td><td class="{('up' if r10>=50 else 'down')}">{r10:.1f}%</td></tr>
<tr><td>TOP20</td><td>{h20}/{t20}</td><td class="{('up' if r20>=50 else 'down')}">{r20:.1f}%</td></tr>
</table>
<div class="note2">单日样本量小（n=100），命中率随行情波动大；今日全市场涨停 63 家（昨日 103 家），情绪转冷，晋级整体偏弱。</div></div>

<div class="panel"><h2>② 分身位命中</h2>
<table><tr><th>身位</th><th>样本</th><th>命中率</th><th>参考</th></tr>{b_rows}</table></div>

<div class="panel"><h2>③ 校准检验（预测概率档 vs 实际命中率）</h2>
<table><tr><th>预测档</th><th>样本</th><th>预测均值</th><th>实际命中率</th><th>偏差</th></tr>{cal_rows}</table>
<div class="note2">单日观察：A+档(≥50%) 今天 4 中 1（25%），低于一年回测的 56%——3板今日仅南华生物晋级；&lt;20% 档 8 中 3 属运气波动。单日不能定结论，但提示：市场转冷日高身位晋级率会明显回落。</div></div>

<div class="panel"><h2>④ 重点个股观察</h2>
<table><tr><th>#</th><th>股票</th><th>预测概率</th><th>综合分</th><th>预测理由</th><th>结果</th></tr>{watch_rows}</table>
<div class="note2">南华生物（TOP1）如期 3→4 板；新华传媒（用户关注的重组股，预测 25.2%）今日晋级 2 板；华软科技/龙头股份/会稽山等高预期股未晋级——高身位单日晋级波动大。</div></div>

<div class="panel"><h2>⑤ 全部命中明细（22 只）</h2>
<table><tr><th>#</th><th>股票</th><th>预测概率</th><th>综合分</th><th>预测理由</th><th>结果</th></tr>{hit_rows}</table></div>

<div class="panel"><h2>⑥ 结论与局限</h2>
<ul>
<li><b>TOP1 命中</b>：概率排序口径（v3.1）上线后首个交易日，第 1 名南华生物兑现 3→4 板。</li>
<li><b>整体 22%</b>：接近一年回测全池基准 20.7%，单日波动正常；今日市场涨停家数 103→63 明显降温，晋级环境偏弱。</li>
<li><b>校准观察</b>：高概率档今天欠收（3板仅 1 只晋级），低概率档 3 只晋级属样本运气；需累计多日才能评估校准质量。</li>
<li>局限：单日复盘 n=100，统计意义有限；模型概率反映的是"一年平均条件下的条件频率"，单日实现围绕期望值大幅波动。</li>
<li>建议：连续记录每日命中，形成滚动命中曲线后再评估调参。</li>
</ul></div>
</div></body></html>"""

with open("review_20260922.html", "w", encoding="utf-8") as f:
    f.write(html)
print("review_20260922.html written")

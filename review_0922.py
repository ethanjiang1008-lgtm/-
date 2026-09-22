# -*- coding: utf-8 -*-
"""复盘 2026-09-21 预测 → 2026-09-22 实际命中。

从 daily_prediction_v3_20260921.html 提取昨日榜单（rank/code/name/boards/prob/score/event/reason），
用东财涨停池判定今日是否继续涨停（命中=次日仍涨停，与回测口径一致）。
"""
import re
import sys
import time
import pandas as pd

sys.path.insert(0, ".")
import data_fetcher as F

HTML = "daily_prediction_v3_20260921.html"
PRED_DATE = "2026-09-21"
TODAY = "2026-09-22"

# ── 1. 解析昨日预测网页 ─────────────────────────────
raw = open(HTML, encoding="utf-8").read()
rows = re.findall(
    r"<td class='rank'>(\d+)</td><td><b>([^<]+)</b><br><span class='note'>(\d+) · ([^·]+) · (\d+)板</span></td>"
    r"<td><span class=\"bar\"[^>]*></span><span class=\"prob\">([\d.]+)%</span><br><span class=\"pill p[ABCD]+\">[^<]*</span></td>"
    r"<td>([\d.]+)</td><td>(.*?)</td></tr>",
    raw, re.S,
)
pred = []
for r in rows:
    rank, name, code, industry, boards, prob, score, reason_td = r
    ev = ""
    m = re.search(r"<span class=\"tag ev\">([^<]+)</span>", reason_td)
    if m:
        ev = m.group(1)
    reason = re.sub(r"<[^>]+>", "", reason_td).strip()
    pred.append({
        "rank": int(rank), "code": code, "name": name.strip(),
        "industry": industry.strip(), "boards": int(boards),
        "prob": float(prob) / 100.0, "score": float(score),
        "event": ev, "reason": reason,
    })
df = pd.DataFrame(pred)
print(f"解析昨日预测: {len(df)} 只 (rank 1..{df['rank'].max()})")
assert len(df) == 100, f"期望 100 只, 实际 {len(df)}"

# ── 2. 今日涨停池 ────────────────────────────────────
pool = F.limit_up_pool(TODAY)
print(f"今日 {TODAY} 涨停池: {len(pool)} 只")
if pool.empty:
    print("!! 今日涨停池为空——可能未收盘/非交易日/接口未更新")
    sys.exit(1)
pool["代码"] = pool["代码"].astype(str).str.strip().str.zfill(6)
zt_codes = set(pool["代码"])
pool_by_code = pool.set_index("代码")

# 今日连板数映射（东财涨停池的连板数=截至今日的连板数）
today_boards = {}
for c, r in pool_by_code.iterrows():
    try:
        today_boards[c] = int(r.get("连板数", 0))
    except Exception:
        today_boards[c] = 0

df["hit"] = df["code"].isin(zt_codes)
df["今日连板数"] = df["code"].map(today_boards).fillna(0).astype(int)
df["晋级"] = df.apply(
    lambda r: "晋级" if r["hit"] and r["今日连板数"] == r["boards"] + 1
    else ("涨停(连板数未递增)" if r["hit"] else "未涨停"), axis=1)

# ── 3. 统计 ─────────────────────────────────────────
print("\n=== 总览 ===")
total = len(df)
hits = int(df["hit"].sum())
print(f"预测 {total} 只 → 今日涨停 {hits} 只 → 命中率 {hits/total*100:.2f}%")

def top_stats(n):
    t = df.head(n)
    h = int(t["hit"].sum())
    return f"TOP{n}: {h}/{len(t)} = {h/len(t)*100:.2f}%"

for n in (1, 3, 5, 10, 20):
    print(top_stats(n))

print("\n=== 分身位 ===")
for b, g in df.groupby("boards"):
    h = int(g["hit"].sum())
    print(f"{b}板: {h}/{len(g)} = {h/len(g)*100:.2f}%")

print("\n=== 分概率档（校准检验）===")
for lo, hi, label in [(0.50, 1.0, "≥50%(A+档)"), (0.30, 0.50, "30-50%(B档)"),
                      (0.20, 0.30, "20-30%(C档)"), (0.0, 0.20, "<20%(D档)")]:
    g = df[(df["prob"] >= lo) & (df["prob"] < hi)]
    if len(g) == 0:
        continue
    h = int(g["hit"].sum())
    avg_p = g["prob"].mean()
    print(f"{label}: n={len(g)} 预测均值{avg_p*100:.1f}% 实际{h/len(g)*100:.1f}%")

print("\n=== 命中股票明细 ===")
hit_df = df[df["hit"]].copy()
for _, r in hit_df.iterrows():
    print(f"  #{r['rank']:3d} {r['code']} {r['name']:<6s} {r['boards']}板 → {r['今日连板数']}板  预测{r['prob']*100:.1f}%")

print("\n=== 重点观察（TOP10 + 高关注）===")
watch = pd.concat([df.head(10), df[df["name"].isin(["新华传媒", "华锡有色", "南华生物", "会稽山"])]])
for _, r in watch.drop_duplicates("code").iterrows():
    print(f"  #{r['rank']:3d} {r['code']} {r['name']:<6s} {r['boards']}板  预测{r['prob']*100:.1f}%  综合分{r['score']}  今日: {r['晋级']}")

# 保存供网页生成
df.to_csv("review_0922_detail.csv", index=False, encoding="utf-8-sig")
print("\n已保存 review_0922_detail.csv")

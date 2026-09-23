# -*- coding: utf-8 -*-
"""算法迭代实验 v4：规则约束 × 校准排序 组合搜索。
候选策略：
  E1: log_amt 校准（当前最强基线）
  E2: log_amt 校准 + 换手<5% 过滤
  E3: log_amt 校准 + 换手<3% 过滤
  E4: 2-3板子池 + turn 校准（只做中位连板）
  E5: 2-3板子池 + 换手升序（纯规则）
  E6: log_amt 校准 + vol_ratio<6 过滤（排除天量分歧）
  E7: log_amt 校准 + 换手<5% + vol<6 双重过滤
"""
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S["b_bucket"] = S["boards"].clip(upper=4)
SPLIT = pd.Timestamp("2026-03-01")
TR = S[S["date"] < SPLIT].copy()
NB = 5

g = S.groupby("b_bucket")
S["q_turn_low"] = 1 - g["turn"].rank(pct=True)
S["q_logamt"] = g["log_amt"].rank(pct=True)

def calib_fit(train, score):
    t = pd.DataFrame({"b": train["b_bucket"].values, "s": score, "y": train["y"].values})
    t["q"] = t.groupby("b")["s"].rank(pct=True)
    t["bin"] = (t["q"] * NB).astype(int).clip(0, NB - 1)
    agg = t.groupby(["b", "bin"])["y"].agg(["mean", "size"]).reset_index()
    return agg.assign(rate=agg["mean"].fillna(0))[["b", "bin", "rate", "size"]]

def calib_apply(sub, score, calib):
    t = pd.DataFrame({"b": sub["b_bucket"].values, "s": score})
    t["q"] = t.groupby("b")["s"].rank(pct=True)
    t["bin"] = (t["q"] * NB).astype(int).clip(0, NB - 1)
    t = t.merge(calib, on=["b", "bin"], how="left")
    return t["rate"].fillna(0).values

def topn(sub, score_col, tops=(1, 2, 3, 5)):
    g = sub.copy()
    rng = np.random.RandomState(7)
    g["_rnd"] = rng.rand(len(g))
    g = g.sort_values(["date", score_col, "_rnd"], ascending=[True, False, True])
    g["_rank"] = g.groupby("date").cumcount() + 1
    out = {}
    for n in tops:
        pos = g[g["_rank"] == n]; pool = g[g["_rank"] <= n]
        out[n] = {"pos_all": pos["y"].mean() * 100,
                  "pos_tr": pos[pos["date"] < SPLIT]["y"].mean() * 100,
                  "pos_va": pos[pos["date"] >= SPLIT]["y"].mean() * 100,
                  "pool_all": pool["y"].mean() * 100}
    return out

CALIB_LA = calib_fit(TR, S.loc[TR.index, "log_amt"].values)

strategies = [
    ("E1 log_amt校准(基线)", S["boards"] <= 3, None),
    ("E2 +换手<5%过滤", S["boards"] <= 3, S["turn"] < 5),
    ("E3 +换手<3%过滤", S["boards"] <= 3, S["turn"] < 3),
    ("E5 2-3板+换手升序", S["boards"].between(2, 3), None),
    ("E6 +放量<6过滤", S["boards"] <= 3, S["vol_ratio"] < 6),
    ("E7 +换手<5且放量<6", S["boards"] <= 3, (S["turn"] < 5) & (S["vol_ratio"] < 6)),
]

print("═══ 策略对比（低位池，log_amt校准×过滤约束）═══")
for tag, pool_mask, filt in strategies:
    sub = S[pool_mask].copy()
    if filt is not None:
        sub = sub[filt]
    # 过滤后重新校准（在过滤子集内校准更准）
    tr_idx = sub[sub["date"] < SPLIT].index
    calib = calib_fit(TR.loc[TR.index.isin(sub.index)], sub.loc[tr_idx, "log_amt"].values) if len(tr_idx) else calib_fit(TR, S.loc[TR.index, "log_amt"].values)
    sub["_prob"] = calib_apply(sub, sub["log_amt"].values, calib)
    rep = topn(sub, "_prob")
    ndays = sub["date"].nunique()
    print(f"  {tag:<24s} TOP1 {rep[1]['pos_all']:5.1f}% (训{rep[1]['pos_tr']:4.1f}/验{rep[1]['pos_va']:4.1f})  TOP3 {rep[3]['pos_all']:5.1f}%  池1-5 {rep[5]['pool_all']:5.1f}%  出手{ndays}日")

# E4: 2-3板子池 + turn 校准
print("\n═══ E4: 2-3板子池 × turn 校准 ═══")
sub = S[S["boards"].between(2, 3)].copy()
tr_idx = sub[sub["date"] < SPLIT].index
calib_t = calib_fit(TR.loc[TR.index.isin(sub.index)], sub.loc[tr_idx, "turn"].values)
sub["_prob"] = calib_apply(sub, sub["turn"].values, calib_t)
rep = topn(sub, "_prob")
print(f"  TOP1 {rep[1]['pos_all']:.1f}% (训{rep[1]['pos_tr']:.1f}/验{rep[1]['pos_va']:.1f})  TOP3 {rep[3]['pos_all']:.1f}%  池1-5 {rep[5]['pool_all']:.1f}%  出手{sub['date'].nunique()}日")

# 首板池专项：换手过滤 × 放量
print("\n═══ 首板池专项 ═══")
fb = S[S["boards"] == 1]
for tag, filt in [("首板全池", None), ("首板+换手<5", fb["turn"] < 5), ("首板+换手<3", fb["turn"] < 3),
                  ("首板+放量<3", fb["vol_ratio"] < 3), ("首板+放量2-5", fb["vol_ratio"].between(2, 5)),
                  ("首板+放量≥5", fb["vol_ratio"] >= 5)]:
    sub = fb if filt is None else fb[filt]
    tr_idx = sub[sub["date"] < SPLIT].index
    calib = calib_fit(TR.loc[TR.index.isin(sub.index)], sub.loc[tr_idx, "log_amt"].values)
    sub = sub.copy()
    sub["_prob"] = calib_apply(sub, sub["log_amt"].values, calib)
    rep = topn(sub, "_prob")
    print(f"  {tag:<14s} TOP1 {rep[1]['pos_all']:5.1f}% (验{rep[1]['pos_va']:4.1f})  TOP3 {rep[3]['pos_all']:5.1f}%  池1-5 {rep[5]['pool_all']:5.1f}%  出手{sub['date'].nunique()}日")

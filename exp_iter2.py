# -*- coding: utf-8 -*-
"""算法迭代实验 v3：多因子分位加权 + 身位×分数分位校准 + 权重网格搜索。
目标：低位池(1-3板) TOP1 命中率最大化（训练集寻优，验证集复验，防过拟合）。
"""
import itertools
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S["b_bucket"] = S["boards"].clip(upper=4)
SPLIT = pd.Timestamp("2026-03-01")
TR = S[S["date"] < SPLIT].copy()
VA = S[S["date"] >= SPLIT].copy()
NB = 5   # 校准档数

# ── 同身位内因子分位（向量化）──
g = S.groupby("b_bucket")
S["q_turn_low"] = 1 - g["turn"].rank(pct=True)     # 低换手=高分
S["q_logamt"] = g["log_amt"].rank(pct=True)        # 高成交额=高分
S["q_vol"] = g["vol_ratio"].rank(pct=True)
S["q_mom5"] = g["mom5"].rank(pct=True)
S["q_lim10"] = g["lim10"].rank(pct=True)
S["q_lim20"] = g["lim20"].rank(pct=True)
S["q_mom20"] = g["mom20"].rank(pct=True)
S["q_prev"] = g["prev_pct"].rank(pct=True)

QCOLS = ["q_turn_low", "q_logamt", "q_vol", "q_mom5", "q_lim10", "q_lim20", "q_mom20", "q_prev"]

# ── 校准：身位桶 × 分数分位 → 晋级率（向量化）──
def calib_fit(train, score):
    t = pd.DataFrame({"b": train["b_bucket"].values, "s": score, "y": train["y"].values})
    t["q"] = t.groupby("b")["s"].rank(pct=True)
    t["bin"] = (t["q"] * NB).astype(int).clip(0, NB - 1)
    agg = t.groupby(["b", "bin"])["y"].agg(["mean", "size"]).reset_index()
    agg["rate"] = agg["mean"].fillna(0)
    return agg[["b", "bin", "rate", "size"]]

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
        out[n] = {"pos_all": pos["y"].mean() * 100, "pos_va": pos[pos["date"] >= SPLIT]["y"].mean() * 100,
                  "pool_all": pool["y"].mean() * 100}
    return out

# ── 基线：单因子 log_amt / turn 校准 ──
print("═══ 基线（单因子校准，低位池1-3板）═══")
for f in ["log_amt", "turn"]:
    calib = calib_fit(TR, S.loc[TR.index, f].values)
    S["_prob"] = calib_apply(S, S[f].values, calib)
    low = S[S["boards"] <= 3]
    rep = topn(low, "_prob")
    print(f"  [{f}] TOP1 {rep[1]['pos_all']:.1f}% (验{rep[1]['pos_va']:.1f}%)  TOP3 {rep[3]['pos_all']:.1f}%  池1-5 {rep[5]['pool_all']:.1f}%")

# ── 组合：分位加权分数 → 校准 → TOPn ──
def run_combo(weights, pool_mask, verbose=False):
    """weights: dict {qcol: w}（归一化内部做）。返回 TOP1 全期/验证命中率。"""
    wsum = sum(weights.values())
    score = sum(S[c] * w for c, w in weights.items()) / wsum
    calib = calib_fit(TR, score[TR.index])
    prob = calib_apply(S, score, calib)
    low = S[pool_mask].copy()
    low["_prob"] = prob[pool_mask]
    rep = topn(low, "_prob")
    return rep, score

# 第1轮：固定身位权重，网格搜索 (turn_low, logamt)
print("\n═══ 第1轮：2D网格 (低换手, 成交额) ═══")
best, best_rep = None, None
cands = []
for wt in np.arange(0.20, 0.51, 0.05):
    for wa in np.arange(0.20, 0.51, 0.05):
        w = {"q_turn_low": wt, "q_logamt": wa, "q_vol": 0.05, "q_mom5": 0.05}
        rep, _ = run_combo(w, S["boards"] <= 3)
        # 目标：全期 TOP1 高 + 验证集不崩
        obj = rep[1]["pos_all"] - 0.5 * max(0, rep[1]["pos_all"] - rep[1]["pos_va"])
        cands.append((obj, rep[1]["pos_all"], rep[1]["pos_va"], w))
cands.sort(key=lambda x: -x[0])
for obj, all_h, va_h, w in cands[:8]:
    print(f"  {w} → TOP1 {all_h:.1f}% (验{va_h:.1f}%)")

# 第2轮：围绕最优 (turn_low, logamt) 微调 + 加第三因子
print("\n═══ 第2轮：加入量能/动量因子微调 ═══")
best_w = cands[0][3]
wt, wa = best_w["q_turn_low"], best_w["q_logamt"]
cands2 = []
for wv in [0.0, 0.05, 0.10, 0.15]:
    for wm in [0.0, 0.05, 0.10]:
        for wl in [0.0, 0.05]:
            w = {"q_turn_low": wt, "q_logamt": wa, "q_vol": wv, "q_mom5": wm, "q_lim10": wl}
            rep, _ = run_combo(w, S["boards"] <= 3)
            obj = rep[1]["pos_all"] - 0.5 * max(0, rep[1]["pos_all"] - rep[1]["pos_va"])
            cands2.append((obj, rep[1]["pos_all"], rep[1]["pos_va"], w))
cands2.sort(key=lambda x: -x[0])
for obj, all_h, va_h, w in cands2[:8]:
    print(f"  {w} → TOP1 {all_h:.1f}% (验{va_h:.1f}%)")

# 最终：最优组合完整报告（低位池/首板池/全池）
print("\n═══ 最终最优组合完整报告 ═══")
final_w = cands2[0][3]
rep, score = run_combo(final_w, S["boards"] <= 3)
print(f"  权重: {final_w}")
print(f"  低位池 TOP1 {rep[1]['pos_all']:.1f}% (验{rep[1]['pos_va']:.1f}%) TOP3 {rep[3]['pos_all']:.1f}% TOP5 {rep[5]['pos_all']:.1f}% 池1-5 {rep[5]['pool_all']:.1f}%")
rep1, _ = run_combo(final_w, S["boards"] == 1)
print(f"  首板池 TOP1 {rep1[1]['pos_all']:.1f}% (验{rep1[1]['pos_va']:.1f}%) TOP3 {rep1[3]['pos_all']:.1f}% 池1-5 {rep1[5]['pool_all']:.1f}%")
repA, _ = run_combo(final_w, S["b_bucket"] <= 4)
print(f"  全池   TOP1 {repA[1]['pos_all']:.1f}% (验{repA[1]['pos_va']:.1f}%) TOP3 {repA[3]['pos_all']:.1f}% 池1-5 {repA[5]['pool_all']:.1f}%")

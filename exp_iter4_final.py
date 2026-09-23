# -*- coding: utf-8 -*-
"""验证 E6（log_amt校准+放量<6）TOP1 构成 + v3 vs v4 完整对比表。"""
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S["b_bucket"] = S["boards"].clip(upper=4)
SPLIT = pd.Timestamp("2026-03-01")
TR = S[S["date"] < SPLIT].copy()
NB = 5
g = S.groupby("b_bucket")

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
    gg = sub.copy()
    rng = np.random.RandomState(7)
    gg["_rnd"] = rng.rand(len(gg))
    gg = gg.sort_values(["date", score_col, "_rnd"], ascending=[True, False, True])
    gg["_rank"] = gg.groupby("date").cumcount() + 1
    out = {}
    for n in tops:
        pos = gg[gg["_rank"] == n]; pool = gg[gg["_rank"] <= n]
        out[n] = {"pos_all": pos["y"].mean() * 100,
                  "pos_tr": pos[pos["date"] < SPLIT]["y"].mean() * 100,
                  "pos_va": pos[pos["date"] >= SPLIT]["y"].mean() * 100,
                  "pool_all": pool["y"].mean() * 100}
    return out

# ── v4-E6：低位池 log_amt校准 + 放量<6 ──
low = S[(S["boards"] <= 3) & (S["vol_ratio"] < 6)].copy()
tr_idx = low[low["date"] < SPLIT].index
calib = calib_fit(TR.loc[TR.index.isin(low.index)], low.loc[tr_idx, "log_amt"].values)
low["_prob"] = calib_apply(low, low["log_amt"].values, calib)
rng = np.random.RandomState(7); low["_rnd"] = rng.rand(len(low))
low = low.sort_values(["date", "_prob", "_rnd"], ascending=[True, False, True])
low["_rank"] = low.groupby("date").cumcount() + 1
top1 = low[low["_rank"] == 1]
print("E6 TOP1 构成: 身位分布", top1["boards"].value_counts().sort_index().to_dict())
print("E6 TOP1 换手分布: <2%:", (top1["turn"] < 2).mean()*100, " <5%:", (top1["turn"] < 5).mean()*100, " ≥15%:", (top1["turn"] >= 15).mean()*100)
print("E6 TOP1 概率均值: %.1f%%  (校准率)" % (top1["_prob"].mean()*100))

# 样例
va = top1[top1["date"] >= SPLIT]
print("\n验证期 TOP1 样例（前15日）:")
print(va[["date", "code", "boards", "turn", "log_amt", "vol_ratio", "_prob", "y"]].head(15).to_string(index=False))

# ── v3 vs v4 完整对比 ──
print("\n═══ v3 vs v4 完整对比（主板口径）═══")
def v3_score(r):
    import model_v3 as M3
    return (M3._f_board(r["boards"]) * 0.30 + M3._f_lim(r["lim10"]) * 0.20
            + M3._f_mom(r["mom5"]) * 0.15 + M3._f_turn(r["turn"]) * 0.15
            + M3._f_vol(r["vol_ratio"]) * 0.10 + M3._f_mood(r["total_lim"]) * 0.10)
S["v3score"] = S.apply(v3_score, axis=1)
TRv3 = S[S["date"] < SPLIT]
calib_v3 = calib_fit(TRv3, S.loc[TRv3.index, "v3score"].values)
S["_p3"] = calib_apply(S, S["v3score"].values, calib_v3)

# v4 首板策略：首板 + 换手<3 + log_amt校准
fb = S[(S["boards"] == 1) & (S["turn"] < 3)].copy()
tri = fb[fb["date"] < SPLIT].index
calib_fb = calib_fit(TR.loc[TR.index.isin(fb.index)], fb.loc[tri, "log_amt"].values)
fb["_p4"] = calib_apply(fb, fb["log_amt"].values, calib_fb)

rows = [("v3 全池", S, "_p3"),
        ("v3 低位池(1-3板)", S[S["boards"] <= 3], "_p3"),
        ("v3 首板池", S[S["boards"] == 1], "_p3"),
        ("v4 低位池(放量<6)", low, "_prob"),
        ("v4 首板池(换手<3)", fb, "_p4")]
for tag, sub, col in rows:
    rep = topn(sub, col)
    print(f"  {tag:<22s} TOP1 {rep[1]['pos_all']:5.1f}% (训{rep[1]['pos_tr']:4.1f}/验{rep[1]['pos_va']:4.1f})  "
          f"TOP2 {rep[2]['pos_all']:5.1f}%  TOP3 {rep[3]['pos_all']:5.1f}%  TOP5 {rep[5]['pos_all']:5.1f}%  "
          f"池1-5 {rep[5]['pool_all']:5.1f}%")

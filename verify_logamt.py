# -*- coding: utf-8 -*-
"""验证 log_amt 低位池 TOP1 的股票构成。"""
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S["b_bucket"] = S["boards"].clip(upper=4)
SPLIT = pd.Timestamp("2026-03-01")
TR = S[S["date"] < SPLIT].copy()

def fit_calib(train, factor, nbuckets=5):
    t = train.copy()
    t["q"] = t.groupby("b_bucket")[factor].rank(pct=True)
    edges = {b: np.linspace(0, 1, nbuckets + 1) for b in sorted(t["b_bucket"].unique())}
    calib = {}
    for b, gb in t.groupby("b_bucket"):
        for i in range(nbuckets):
            lo, hi = edges[b][i], edges[b][i + 1]
            seg = gb[(gb["q"] > lo) & (gb["q"] <= hi)] if i > 0 else gb[gb["q"] <= hi]
            if i == nbuckets - 1:
                seg = gb[gb["q"] > lo]
            calib[(b, i)] = {"lo": lo, "hi": hi, "rate": seg["y"].mean() if len(seg) else np.nan, "n": len(seg)}
    return calib, edges

def apply_calib(sub, factor, calib, nbuckets=5):
    s = sub.copy()
    s["q"] = s.groupby("b_bucket")[factor].rank(pct=True)
    probs = []
    for _, r in s.iterrows():
        b = int(r["b_bucket"]); q = r["q"]; best = None
        for i in range(nbuckets):
            seg = calib.get((b, i))
            if seg is None: continue
            lo, hi = seg["lo"], seg["hi"]
            if i == 0 and q <= hi: best = seg; break
            if 0 < i < nbuckets - 1 and lo < q <= hi: best = seg; break
            if i == nbuckets - 1 and q > lo: best = seg; break
        probs.append(best["rate"] if best else np.nan)
    s["prob"] = probs
    return s

calib, _ = fit_calib(TR, "log_amt")
SF = apply_calib(S, "log_amt", calib)
low = SF[SF["boards"] <= 3].copy()
rng = np.random.RandomState(7); low["_rnd"] = rng.rand(len(low))
low = low.sort_values(["date", "prob", "log_amt", "_rnd"], ascending=[True, False, False, True])
top1 = low.groupby("date").head(1)
print("log_amt 低位池 TOP1 构成（242日）:")
print("  身位分布:", top1["boards"].value_counts().sort_index().to_dict())
print("  次日连板:", top1["y"].mean()*100, "%")
print("  换手率中位:", top1["turn"].median(), " 成交额中位(亿):", (top1["log_amt"]/8).median())
print("\n  TOP1 中 y=1 的样例（验证期前20）:")
va = top1[top1["date"] >= SPLIT]
print(va[["date", "code", "boards", "turn", "log_amt", "prob", "y"]].head(20).to_string())
print("\n  TOP1 中 y=0 的样例（验证期前20）:")
print(va[va["y"] == 0][["date", "code", "boards", "turn", "log_amt", "prob", "y"]].head(20).to_string())

# 看 turn 校准表方向：高换手还是低换手晋级率高
calib_t, _ = fit_calib(TR, "turn")
print("\n  turn 校准表（身位桶1/2/3 × 分位格 晋级率）:")
for b in [1, 2, 3]:
    row = [f"{calib_t[(b,i)]['rate']*100:.0f}%" for i in range(5)]
    print(f"  身位{b}: " + " ".join(row))

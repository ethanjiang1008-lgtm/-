# -*- coding: utf-8 -*-
"""生成 calib_v4.json：训练集（2025-09-22~2026-03-01）拟合
low（1-3板, 放量<6）与 fb（首板, 换手<3）两套 log_amt 身位桶内分位校准表。"""
import json
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S["b_bucket"] = S["boards"].clip(upper=4)
SPLIT = pd.Timestamp("2026-03-01")
TR = S[S["date"] < SPLIT].copy()
NB = 5

def fit(sub):
    """返回 {桶: [NB个晋级率]}"""
    t = sub.copy()
    t["_bucket"] = t["boards"].apply(lambda b: str(int(b) if int(b) <= 3 else 4))
    t["_q"] = t.groupby("_bucket")["log_amt"].rank(pct=True)
    t["_bin"] = (t["_q"] * NB).astype(int).clip(0, NB - 1)
    out = {}
    for b, gb in t.groupby("_bucket"):
        rates = [gb[gb["_bin"] == i]["y"].mean() for i in range(NB)]
        out[b] = [round(float(r), 4) if not np.isnan(r) else 0.0 for r in rates]
    return out

low_calib = fit(TR[(TR["boards"] <= 3) & (TR["vol_ratio"] < 6)])
fb_calib = fit(TR[(TR["boards"] == 1) & (TR["turn"] < 3)])

calib = {"low": low_calib, "fb": fb_calib}
with open("calib_v4.json", "w", encoding="utf-8") as f:
    json.dump(calib, f, ensure_ascii=False, indent=1)
print("calib_v4.json 已生成")
print("low:", json.dumps(low_calib, ensure_ascii=False))
print("fb:", json.dumps(fb_calib, ensure_ascii=False))

# 校验：用校准表回放全期 TOP1（应 ≈65%）
def replay(mode, mask):
    from model_v4 import prob_from_calib
    sub = S[mask].copy()
    sub["_bucket"] = sub["boards"].apply(lambda b: str(int(b) if int(b) <= 3 else 4))
    sub["_q"] = sub.groupby("_bucket")["log_amt"].rank(pct=True)
    sub["prob"] = sub.apply(lambda r: prob_from_calib(mode, r["boards"], r["_q"]) * 100, axis=1)
    rng = np.random.RandomState(7); sub["_rnd"] = rng.rand(len(sub))
    sub = sub.sort_values(["date", "prob", "_rnd"], ascending=[True, False, True])
    sub["_rank"] = sub.groupby("date").cumcount() + 1
    t1 = sub[sub["_rank"] == 1]
    va = t1[t1["date"] >= SPLIT]
    print(f"[回放] {mode}: TOP1 全期 {t1['y'].mean()*100:.1f}% / 验证 {va['y'].mean()*100:.1f}%")

replay("low", (S["boards"] <= 3) & (S["vol_ratio"] < 6))
replay("fb", (S["boards"] == 1) & (S["turn"] < 3))

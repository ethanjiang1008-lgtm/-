# -*- coding: utf-8 -*-
"""算法迭代实验 v2：沪深主板（非ST/科创/创业）涨停样本上的策略对比。

统一口径（与 v3 报告可比）：
- 每日按"概率"排序取 TOPn（同概率用因子值/分数破平局）
- 概率 = 身位桶 × 因子分位 校准（在训练集拟合，验证集评估）
- 命中 = 次日继续涨停；输出 全期/训练/验证 命中率
"""
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S = S.sort_values(["date", "code"]).reset_index(drop=True)
S["b_bucket"] = S["boards"].clip(upper=4)          # 身位桶 1/2/3/4+

SPLIT = pd.Timestamp("2026-03-01")                 # 与 v3 报告一致的切分点
TR = S[S["date"] < SPLIT].copy()
VA = S[S["date"] >= SPLIT].copy()
print(f"主板样本 {len(S)} 条 / {S['date'].nunique()} 日 | 训练 {len(TR)} / 验证 {len(VA)}")
print(f"基准晋级率: 全期 {S['y'].mean()*100:.1f}% | 训练 {TR['y'].mean()*100:.1f}% | 验证 {VA['y'].mean()*100:.1f}%\n")


def fit_calib(train, factor, nbuckets=5):
    """训练集拟合 (身位桶 × 因子分位) → 晋级率表。返回 calib dict + 分位边界。"""
    t = train.copy()
    t["q"] = t.groupby("b_bucket")[factor].rank(pct=True)   # 同身位内因子分位
    edges = {b: np.linspace(0, 1, nbuckets + 1) for b in sorted(t["b_bucket"].unique())}
    calib = {}
    for b, gb in t.groupby("b_bucket"):
        for i in range(nbuckets):
            lo, hi = edges[b][i], edges[b][i + 1]
            seg = gb[(gb["q"] > lo) & (gb["q"] <= hi)] if i > 0 else gb[gb["q"] <= hi]
            if i == nbuckets - 1:
                seg = gb[gb["q"] > lo]
            rate = seg["y"].mean() if len(seg) else np.nan
            calib[(b, i)] = {"lo": lo, "hi": hi, "rate": rate, "n": len(seg)}
    return calib, edges


def apply_calib(sub, factor, calib, nbuckets=5):
    """给样本赋校准概率：同身位内因子分位落入哪格 → 该格晋级率。"""
    s = sub.copy()
    s["q"] = s.groupby("b_bucket")[factor].rank(pct=True)
    probs = []
    for _, r in s.iterrows():
        b = int(r["b_bucket"])
        q = r["q"]
        # 找所在格
        best = None
        for i in range(nbuckets):
            seg = calib.get((b, i))
            if seg is None:
                continue
            lo, hi = seg["lo"], seg["hi"]
            if i == 0 and q <= hi:
                best = seg; break
            if 0 < i < nbuckets - 1 and lo < q <= hi:
                best = seg; break
            if i == nbuckets - 1 and q > lo:
                best = seg; break
        probs.append(best["rate"] if best else np.nan)
    s["prob"] = probs
    return s


def topn_report(sub, prob_col="prob", tie_col=None, tops=(1, 2, 3, 5)):
    """每日按 prob 排序取 TOPn，输出位次命中率与池命中率（全期/训练/验证）。"""
    g = sub.copy()
    rng = np.random.RandomState(7)
    g["_rnd"] = rng.rand(len(g))
    asc = [True, False, True]
    cols = ["date", prob_col, "_rnd"]
    g = g.sort_values(cols, ascending=asc)
    g["_rank"] = g.groupby("date").cumcount() + 1
    out = {}
    for n in tops:
        pos = g[g["_rank"] == n]
        pool = g[g["_rank"] <= n]
        def _hr(d):
            return d["y"].mean() * 100 if len(d) else np.nan
        out[n] = {"pos_all": _hr(pos), "pos_tr": _hr(pos[pos["date"] < SPLIT]),
                  "pos_va": _hr(pos[pos["date"] >= SPLIT]),
                  "pool_all": _hr(pool), "pool_tr": _hr(pool[pool["date"] < SPLIT]),
                  "pool_va": _hr(pool[pool["date"] >= SPLIT])}
    return out


def line(tag, rep, low_only=False):
    p1 = rep[1]
    return (f"{tag:<38s} TOP1 {p1['pos_all']:5.1f}% (训{p1['pos_tr']:4.1f}/验{p1['pos_va']:4.1f})  "
            f"TOP3 {rep[3]['pos_all']:5.1f}%  TOP5 {rep[5]['pos_all']:5.1f}%  "
            f"池1-5 {rep[5]['pool_all']:5.1f}%")


FACTORS = ["boards", "turn", "mom5", "mom20", "lim10", "lim20", "vol_ratio", "log_amt", "prev_pct"]

# ─── S0: v3 基线（六因子分数 → 分身位×分位校准）───
def v3_score(r):
    import model_v3 as M3
    s = (M3._f_board(r["boards"]) * 0.30 + M3._f_lim(r["lim10"]) * 0.20
         + M3._f_mom(r["mom5"]) * 0.15 + M3._f_turn(r["turn"]) * 0.15
         + M3._f_vol(r["vol_ratio"]) * 0.10 + M3._f_mood(r["total_lim"]) * 0.10)
    return s

S["v3score"] = S.apply(v3_score, axis=1)
TR = S[S["date"] < SPLIT].copy()      # v3score 加入后重新切分
VA = S[S["date"] >= SPLIT].copy()
calib_v3, _ = fit_calib(TR, "v3score")
SV3 = apply_calib(S, "v3score", calib_v3)
print("═══ S0: v3 基线（六因子+分位校准，主板口径）═══")
for name, sub in [("全池", SV3), ("低位池1-3板", SV3[SV3["boards"] <= 3]),
                  ("首板池", SV3[SV3["boards"] == 1])]:
    rep = topn_report(sub, tie_col="v3score")
    print("  " + line(f"[{name}]", rep))

# ─── S1: 单因子校准（找最强因子）───
print("\n═══ S1: 单因子校准（身位×因子分位）═══")
for f in FACTORS:
    calib_f, _ = fit_calib(TR, f)
    SF = apply_calib(S, f, calib_f)
    rep = topn_report(SF, tie_col=f)
    print("  " + line(f"[单因子] {f}", rep))

print("\n═══ S1b: 单因子校准 × 低位池(1-3板) ═══")
for f in FACTORS:
    calib_f, _ = fit_calib(TR, f)
    SF = apply_calib(S, f, calib_f)
    rep = topn_report(SF[SF["boards"] <= 3], tie_col=f)
    print("  " + line(f"[{f}]", rep))

print("\n═══ S1c: 单因子校准 × 首板池 ═══")
for f in FACTORS:
    calib_f, _ = fit_calib(TR, f)
    SF = apply_calib(S, f, calib_f)
    rep = topn_report(SF[SF["boards"] == 1], tie_col=f)
    print("  " + line(f"[{f}]", rep))

# 保存中间结果
S.to_csv("exp_ready.csv", index=False, encoding="utf-8-sig")

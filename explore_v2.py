# -*- coding: utf-8 -*-
"""v2 策略模拟：在 1 年数据上模拟升级后的评分+过滤规则，验证命中率能否到 50%+。
关键：
1) 首板子集：新因子（动量/涨停频率/新高）对首板晋级的区分能力
2) v2 评分全池 TOP1：加入 mom5/lim10/hi20 后，不同过滤规则的命中率
3) 分段验证：前2/3（训练） vs 后1/3（验证）避免过拟合
"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CACHE = "bs_daily_all.csv"


def load():
    df = pd.read_csv(CACHE, dtype={"code": str})
    df = df.sort_values(["code", "date"]).reset_index(drop=True)

    def thresh(row):
        if row["is_st"]:
            return 9.8 if row["code"].startswith(("3", "68")) else 4.8
        return 19.8 if row["code"].startswith(("3", "68")) else 9.8
    df["thresh"] = df.apply(thresh, axis=1)
    df["is_limit"] = df["pct"] >= df["thresh"] - 1e-6
    df["_grp"] = (~df["is_limit"]).groupby(df["code"]).cumsum()
    df["boards"] = df.groupby(["code", "_grp"])["is_limit"].cumsum().astype(int)
    df = df.drop(columns=["_grp"])
    # 动量
    g = df.groupby("code", sort=False)
    df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
    df["mom10"] = df["close"] / g["close"].shift(10) * 100 - 100
    df["hi20"] = (df["close"] >= g["close"].transform(
        lambda s: s.rolling(20, min_periods=10).max()) - 1e-9)
    df["lim5"] = g["is_limit"].transform(lambda s: s.rolling(5, min_periods=1).sum().shift(1))
    df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))
    return df


def link(df):
    tds = sorted(df["date"].unique())
    tdi = {d: i for i, d in enumerate(tds)}
    lim = df[df["is_limit"]].copy()
    lim["next_date"] = lim["date"].map(lambda d: tds[tdi[d] + 1] if tdi[d] + 1 < len(tds) else None)
    lim = lim[lim["next_date"].notna()]
    nxt = df[["code", "date", "close", "is_limit"]].rename(
        columns={"date": "next_date", "close": "next_close", "is_limit": "next_limit"})
    m = lim.merge(nxt, on=["code", "next_date"], how="left")
    m["ret"] = (m["next_close"] - m["close"]) / m["close"] * 100
    m["hit"] = m["next_limit"].fillna(False)
    return m


def show(title, sub):
    n = len(sub)
    if n == 0:
        print(f"  {title}: n=0")
        return 0
    hit = int(sub["hit"].sum())
    r = hit / n * 100
    print(f"  {title}: n={n:>5} 命中率 {r:5.2f}% 均收 {sub['ret'].mean():+.2f}%")
    return r


def v2_score(pool):
    df = pool.copy()
    df["s_board"] = df["boards"].apply(
        lambda b: 10.0 if b >= 6 else 9.5 if b == 5 else 9.0 if b == 4
        else 8.0 if b == 3 else 7.0 if b == 2 else 5.5)
    n = len(pool)
    mood = 3.0 if n <= 30 else 5.0 if n <= 50 else 7.0 if n <= 70 else 8.0 if n <= 90 else 9.0 if n <= 120 else 10.0
    df["s_mood"] = mood

    def pos(pct):
        if pct >= 19.8:
            return 10.0 if pct >= 19.95 else 9.0
        if pct >= 9.8:
            return 10.0 if pct >= 10.0 else 8.0
        return 6.0
    df["s_pos"] = df["pct"].apply(pos)

    def qual(pct):
        lim = 19.8 if pct >= 19.8 else 9.8
        return max(4.0, 10.0 - abs(pct - (lim + 0.2)) * 10)
    df["s_qual"] = df["pct"].apply(qual)

    def mom_s(x):
        if x >= 50: return 10.0
        if x >= 30: return 9.0
        if x >= 20: return 8.0
        if x >= 10: return 7.0
        if x >= 0: return 6.0
        return 4.0
    df["s_mom"] = df["mom5"].apply(mom_s)

    def lim_s(x):
        if x >= 5: return 10.0
        if x >= 4: return 9.0
        if x >= 3: return 8.0
        if x >= 2: return 7.0
        return 5.0
    df["s_lim"] = df["lim10"].apply(lim_s)

    df["s_hi"] = df["hi20"].map({True: 9.0, False: 6.0})
    df["score"] = (df["s_board"] * .25 + df["s_mood"] * .10 + df["s_pos"] * .15
                   + df["s_qual"] * .10 + df["s_mom"] * .15 + df["s_lim"] * .15
                   + df["s_hi"] * .10) * 10
    return df


def main():
    df = load()
    m = link(df)
    print(f"涨停样本 {len(m)}")

    # ── 首板子集因子分档 ──
    fb = m[m["boards"] == 1]
    print("\n═══ 首板子集（boards==1）：哪些因子能区分次日晋级）═══")
    show("首板整体", fb)
    for lo, hi, lab in [(None, 10, "mom5<10%"), (10, 20, "10-20%"), (20, 30, "20-30%"),
                        (30, None, "≥30%")]:
        show(f"mom5 {lab}", fb[(fb["mom5"] >= lo if lo else True) & (fb["mom5"] < hi if hi else True)])
    for lo, hi, lab in [(None, 2, "lim10 0-1次"), (2, 3, "2次"), (3, 5, "3-4次"), (5, None, "≥5次")]:
        show(f"lim10 {lab}", fb[(fb["lim10"] >= lo if lo else True) & (fb["lim10"] < hi if hi else True)])
    show("20日新高", fb[fb["hi20"]])
    show("非20日新高", fb[~fb["hi20"]])
    fb["n_lim"] = fb["date"].map(fb.groupby("date").size())
    show("涨停<60家", fb[fb["n_lim"] < 60])
    show("涨停60-100", fb[(fb["n_lim"] >= 60) & (fb["n_lim"] < 100)])
    show("涨停≥100", fb[fb["n_lim"] >= 100])

    # 首板子集 + 组合
    show("mom5≥20 且 lim10≥3", fb[(fb["mom5"] >= 20) & (fb["lim10"] >= 3)])
    show("mom5≥30 或 lim10≥5", fb[(fb["mom5"] >= 30) | (fb["lim10"] >= 5)])
    show("mom5≥20 且 20日新高", fb[(fb["mom5"] >= 20) & (fb["hi20"])])

    # ── v2 评分全池 TOP1 ──
    print("\n═══ v2 评分 · 全池 TOP1（每日取最高分）═══")
    rows = []
    for d, g in m.groupby("date"):
        s = v2_score(g).sort_values("score", ascending=False)
        rows.append(s.iloc[0])
    t1 = pd.DataFrame(rows)
    t1["n_lim"] = t1["date"].map(t1.groupby("date").size())
    show("v2 TOP1 整体", t1)
    show("  ├ boards≥5", t1[t1["boards"] >= 5])
    show("  ├ boards≥6", t1[t1["boards"] >= 6])
    show("  ├ score≥85", t1[t1["score"] >= 85])
    show("  ├ score≥88", t1[t1["score"] >= 88])
    show("  ├ boards≥4 且 score≥85", t1[(t1["boards"] >= 4) & (t1["score"] >= 85)])
    show("  ├ boards≥4 且 score≥88", t1[(t1["boards"] >= 4) & (t1["score"] >= 88)])
    show("  ├ boards≥5 或 score≥90", t1[(t1["boards"] >= 5) | (t1["score"] >= 90)])
    show("  └ boards≥5 且 (mom5≥20 或 lim10≥3)", t1[(t1["boards"] >= 5) & ((t1["mom5"] >= 20) | (t1["lim10"] >= 3))])

    # ── 分段验证（不过拟合检查）──
    print("\n═══ 分段验证（前2/3训练 2025-06~2026-02 / 后1/3验证 2026-03~2026-09）═══")
    split = "2026-03-01"
    for name, mask in [("v2 TOP1 整体", pd.Series(True, index=t1.index)),
                       ("boards≥5", t1["boards"] >= 5),
                       ("boards≥4 且 score≥85", (t1["boards"] >= 4) & (t1["score"] >= 85))]:
        tr = t1[mask & (t1["date"] < split)]
        va = t1[mask & (t1["date"] >= split)]
        print(f"\n  {name}:")
        show(f"  训练段 {tr['date'].min()}~{tr['date'].max()}（{len(tr)}笔）", tr)
        show(f"  验证段 {va['date'].min()}~{va['date'].max()}（{len(va)}笔）", va)

    # 空仓率
    print("\n═══ 出手频率（避免过度空仓）═══")
    ndays = t1["date"].nunique()
    for name, mask in [("boards≥5", t1["boards"] >= 5),
                       ("boards≥6", t1["boards"] >= 6),
                       ("boards≥4 且 score≥85", (t1["boards"] >= 4) & (t1["score"] >= 85))]:
        n = int(mask.sum())
        print(f"  {name}: {n} 天出手 / {ndays} 交易日 = 出手率 {n/ndays*100:.0f}%")


if __name__ == "__main__":
    main()

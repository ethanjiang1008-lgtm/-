# -*- coding: utf-8 -*-
"""v4 探索：1-3 板低位池内选股策略。
用户要求：4板以上不做，优先 1-3 板。本脚本回答：
1) 1-3 板池内 v2 评分 TOP1/TOP5 命中率（全期+分段）
2) 哪些因子/过滤组合在 1-3 板池内区分度最强
3) 目标：找到低位池内能到的最好命中率，诚实报告上限"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CACHE = "bs_daily_all.csv"
SPLIT = "2026-03-01"


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
    g = df.groupby("code", sort=False)
    df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
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
    m["hit"] = m["next_limit"].fillna(False)
    m["n_lim"] = m["date"].map(m.groupby("date").size())
    return m


def board_s(b):
    b = int(b)
    if b >= 6:
        return 10.0
    return float({5: 9, 4: 8, 3: 7, 2: 6, 1: 5}.get(b, 5))


def lim_s(x):
    if x >= 5: return 10.0
    if x >= 4: return 9.0
    if x >= 3: return 8.0
    if x >= 2: return 6.5
    return 4.0


def mom_s(x):
    if x >= 50: return 10.0
    if x >= 30: return 9.0
    if x >= 20: return 8.0
    if x >= 10: return 7.0
    if x >= 0: return 5.5
    return 4.0


def pos_s(pct):
    if pct >= 19.8:
        return 10.0 if pct >= 19.95 else 9.0
    if pct >= 9.8:
        return 10.0 if pct >= 10.0 else 8.0
    return 6.0


def qual_s(pct):
    lim = 19.8 if pct >= 19.8 else 9.8
    return max(4.0, 10.0 - abs(pct - (lim + 0.2)) * 10)


def mood_s(n):
    if n <= 30: return 3.0
    if n <= 50: return 5.0
    if n <= 70: return 7.0
    if n <= 90: return 8.0
    if n <= 120: return 9.0
    return 10.0


def v2_score(pool, n_lim):
    df = pool.copy()
    df["s"] = (df["boards"].apply(board_s) * .30 + df["lim10"].apply(lim_s) * .20
               + df["mom5"].apply(mom_s) * .15 + df["pct"].apply(pos_s) * .15
               + df["pct"].apply(qual_s) * .10 + mood_s(n_lim) * .10)
    return df.sort_values("s", ascending=False).reset_index(drop=True)


def show(tag, df, ndays=None):
    n = len(df)
    if n == 0:
        print(f"  {tag}: n=0")
        return
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    line = (f"  {tag}: n={n:>4} 全期 {df['hit'].mean()*100:5.2f}% | "
            f"训练 {tr['hit'].mean()*100:5.2f}%({len(tr)}) / 验证 {va['hit'].mean()*100:5.2f}%({len(va)})")
    if ndays:
        line += f"  出手率 {df['date'].nunique()/ndays*100:.0f}%"
    print(line)


def main():
    df = load()
    m = link(df)
    ndays = m["date"].nunique()
    print(f"涨停样本 {len(m)}，交易日 {ndays}\n")

    print("═══ 0. 自然晋级率（未筛选）═══")
    for b in (1, 2, 3, 4, 5, 6):
        sub = m[m["boards"] == b]
        show(f"{b}板", sub)

    print("\n═══ 1. 1-3 板池（boards≤3，用户指定低位池）═══")
    low = m[m["boards"] <= 3]
    show("1-3板整体", low)
    # v2 评分 TOP
    rows = []
    for d, g in low.groupby("date"):
        s = v2_score(g, len(g))
        rows.append(s.head(5))
    top = pd.concat(rows)
    show("1-3板 v2 TOP1", top.groupby("date").head(1), ndays)
    show("1-3板 v2 TOP5", top, ndays)

    print("\n═══ 2. 1-3 板池内因子区分度 ═══")
    show("lim10≥2", low[low["lim10"] >= 2])
    show("lim10≥3", low[low["lim10"] >= 3])
    show("lim10≥4", low[low["lim10"] >= 4])
    show("mom5≥20", low[low["mom5"] >= 20])
    show("mom5≥30", low[low["mom5"] >= 30])
    show("lim10≥2 且 mom5≥20", low[(low["lim10"] >= 2) & (low["mom5"] >= 20)])
    show("lim10≥3 且 mom5≥15", low[(low["lim10"] >= 3) & (low["mom5"] >= 15)])
    show("lim10≥2 且 涨停<100", low[(low["lim10"] >= 2) & (low["n_lim"] < 100)])

    print("\n═══ 3. 分层看：2板池与3板池的因子效果（抓 2-3 板晋级）═══")
    b2 = m[m["boards"] == 2]
    b3 = m[m["boards"] == 3]
    show("2板整体", b2)
    show("2板 lim10≥2", b2[b2["lim10"] >= 2])
    show("2板 lim10≥3", b2[b2["lim10"] >= 3])
    show("2板 mom5≥20", b2[b2["mom5"] >= 20])
    show("2板 lim10≥2 且 mom5≥15", b2[(b2["lim10"] >= 2) & (b2["mom5"] >= 15)])
    show("3板整体", b3)
    show("3板 lim10≥3", b3[b3["lim10"] >= 3])
    show("3板 mom5≥20", b3[b3["mom5"] >= 20])
    show("3板 lim10≥2 且 mom5≥20", b3[(b3["lim10"] >= 2) & (b3["mom5"] >= 20)])
    show("3板 lim10≥3 且 mom5≥10", b3[(b3["lim10"] >= 3) & (b3["mom5"] >= 10)])

    print("\n═══ 4. TOP1 视角：1-3板内每日最高分 + 过滤 ═══")
    rows1 = []
    for d, g in low.groupby("date"):
        s = v2_score(g, len(g))
        rows1.append(s.iloc[0])
    t1 = pd.DataFrame(rows1)
    show("1-3板 TOP1 全部", t1, ndays)
    show("  ├ lim10≥2", t1[t1["lim10"] >= 2], ndays)
    show("  ├ lim10≥3", t1[t1["lim10"] >= 3], ndays)
    show("  ├ 3板", t1[t1["boards"] == 3], ndays)
    show("  ├ 3板 且 lim10≥2", t1[(t1["boards"] == 3) & (t1["lim10"] >= 2)], ndays)
    show("  └ 3板 且 (lim10≥2 或 mom5≥20)", t1[(t1["boards"] == 3) & ((t1["lim10"] >= 2) | (t1["mom5"] >= 20))], ndays)

    # 首板专项+2-3板混合：按「板数*lim10」代理排序
    print("\n═══ 5. 代理排序（board×lim10 主导）TOP1 ═══")
    low["rk"] = low["boards"] * 10 + low["lim10"].clip(0, 9) + (low["mom5"].clip(0, 50) / 50.0)
    t1r = low.sort_values("rk", ascending=False).groupby("date").head(1)
    show("低位池 TOP1 代理", t1r, ndays)
    show("  ├ 且 3板", t1r[t1r["boards"] == 3], ndays)
    show("  ├ 且 boards≥2", t1r[t1r["boards"] >= 2], ndays)
    show("  └ 且 (lim10≥2 或 boards==3)", t1r[(t1r["lim10"] >= 2) | (t1r["boards"] == 3)], ndays)


if __name__ == "__main__":
    main()

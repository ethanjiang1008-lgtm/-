# -*- coding: utf-8 -*-
"""v5 探索：低位池（1-3板）代理排序 TOP1 的过滤变体，找最高命中率配置。"""
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


def show(tag, df, ndays):
    n = len(df)
    if n == 0:
        print(f"  {tag}: n=0")
        return
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    print(f"  {tag}: n={n:>4} 全期 {df['hit'].mean()*100:5.2f}% | "
          f"训练 {tr['hit'].mean()*100:5.2f}%({len(tr)}) / 验证 {va['hit'].mean()*100:5.2f}%({len(va)})"
          f"  出手率 {df['date'].nunique()/ndays*100:.0f}%")


def main():
    df = load()
    m = link(df)
    ndays = m["date"].nunique()
    low = m[m["boards"] <= 3].copy()
    low["rk"] = low["boards"] * 10 + low["lim10"].clip(0, 9) + (low["mom5"].clip(0, 50) / 50.0)
    t1 = low.sort_values("rk", ascending=False).groupby("date").head(1)

    print(f"低位池样本 {len(low)}，交易日 {ndays}\n")
    print("═══ 代理排序 TOP1 过滤变体（身位×10 + lim10 + mom5）═══")
    show("TOP1 全部", t1, ndays)
    show("TOP1 且 boards==3", t1[t1["boards"] == 3], ndays)
    show("TOP1 且 boards==3 且 lim10≥2", t1[(t1["boards"] == 3) & (t1["lim10"] >= 2)], ndays)
    show("TOP1 且 boards==3 且 lim10≥3", t1[(t1["boards"] == 3) & (t1["lim10"] >= 3)], ndays)
    show("TOP1 且 boards==3 且 mom5≥10", t1[(t1["boards"] == 3) & (t1["mom5"] >= 10)], ndays)
    show("TOP1 且 boards==3 且 mom5≥20", t1[(t1["boards"] == 3) & (t1["mom5"] >= 20)], ndays)
    show("TOP1 且 boards==3 且 涨停<120", t1[(t1["boards"] == 3) & (t1["n_lim"] < 120)], ndays)
    show("TOP1 且 boards>=2 且 lim10≥2", t1[(t1["boards"] >= 2) & (t1["lim10"] >= 2)], ndays)
    show("TOP1 且 (boards==3 或 lim10≥4)", t1[(t1["boards"] == 3) | (t1["lim10"] >= 4)], ndays)
    show("TOP1 且 (boards==3 或 (boards==2 且 lim10≥4))",
         t1[(t1["boards"] == 3) | ((t1["boards"] == 2) & (t1["lim10"] >= 4))], ndays)

    # 3板 TOP2 视角（3板池内按 lim10/mom5 排）
    print("\n═══ 3板池内 TOP（当日有 3 板时选 3 板池内最高分）═══")
    b3 = low[low["boards"] == 3].copy()
    b3t1 = b3.sort_values(["lim10", "mom5"], ascending=False).groupby("date").head(1)
    show("3板池 TOP1", b3t1, ndays)
    show("  ├ lim10≥2", b3t1[b3t1["lim10"] >= 2], ndays)
    show("  ├ lim10≥3", b3t1[b3t1["lim10"] >= 3], ndays)
    show("  ├ mom5≥15", b3t1[b3t1["mom5"] >= 15], ndays)
    show("  └ lim10≥2 且 mom5≥10", b3t1[(b3t1["lim10"] >= 2) & (b3t1["mom5"] >= 10)], ndays)


if __name__ == "__main__":
    main()

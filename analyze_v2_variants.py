# -*- coding: utf-8 -*-
"""v2 变体测试：在缓存上模拟「TOP1 + 身位过滤 + 情绪上限」组合，
输出全期/训练/验证三段命中率，寻找两段都≥50% 的稳健配置。"""
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


def simulate(m, min_boards, mood_cap=None, top_n=1):
    rows = []
    for d, g in m.groupby("date"):
        if mood_cap is not None and len(g) > mood_cap:
            continue
        s = v2_score(g, len(g))
        pick = s.head(top_n)
        if min_boards > 0 and int(pick.iloc[0]["boards"]) < min_boards:
            continue
        rows.append(pick.iloc[:top_n])
    return pd.concat(rows)


def show(tag, df):
    n = len(df)
    if n == 0:
        print(f"  {tag}: n=0")
        return
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    print(f"  {tag}: n={n:>4} 全期 {df['hit'].mean()*100:5.2f}% | "
          f"训练 {tr['hit'].mean()*100:5.2f}%({len(tr)}) / 验证 {va['hit'].mean()*100:5.2f}%({len(va)})")


def main():
    df = load()
    m = link(df)
    ndays = m["date"].nunique()
    print(f"涨停样本 {len(m)}，交易日 {ndays}\n")

    configs = [
        ("TOP1 + 身位≥6", dict(min_boards=6)),
        ("TOP1 + 身位≥6 + 涨停≤100", dict(min_boards=6, mood_cap=100)),
        ("TOP1 + 身位≥6 + 涨停≤120", dict(min_boards=6, mood_cap=120)),
        ("TOP1 + 身位≥5", dict(min_boards=5)),
        ("TOP1 + 身位≥5 + 涨停≤100", dict(min_boards=5, mood_cap=100)),
        ("TOP1 + 身位≥4 + 涨停≤70", dict(min_boards=4, mood_cap=70)),
        ("TOP1 + 身位≥5 + 涨停≤120", dict(min_boards=5, mood_cap=120)),
    ]
    for name, kw in configs:
        r = simulate(m, **kw)
        show(name, r)
        out = int(r["hit"].sum())
        print(f"      → 出手 {r['date'].nunique()}/{ndays} 天，连板 {out} 次")

    # 首板版：lim10 主导 TOP1 + 情绪上限
    print()
    fb = m[m["boards"] == 1]
    fb["s"] = fb["lim10"].apply(lim_s) * 10 + fb["mom5"].apply(mom_s) * 0.5
    for cap in (None, 120, 100):
        sub = fb
        tag = "首板TOP1(lim10主导)"
        if cap is not None:
            sub = fb[fb["n_lim"] <= cap]
            tag += f"+涨停≤{cap}"
        top1 = sub.sort_values("s", ascending=False).groupby("date").head(1)
        show(tag, top1)


if __name__ == "__main__":
    main()

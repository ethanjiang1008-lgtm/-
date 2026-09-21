# -*- coding: utf-8 -*-
"""因子探索：在 1 年全市场日线上重建涨停日历，测试各类因子/规则对
「次日连板」的区分能力，为把命中率提升到 50%+ 找依据。

维度：连板身位 / 当日涨停家数(情绪) / 综合分 / 5日动量 / 20日新高 / 组合规则。
只统计「模型打分后的每日第1名」（全池模式 TOP1）与「全部涨停股」两个视角。
"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CACHE = "bs_daily_all.csv"


def load_market():
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
    return df


def add_momentum(df):
    """5/10日动量 + 20日新高 + 近5日涨停次数（按股票分组向量化）。"""
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    g = df.groupby("code", sort=False)
    df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
    df["mom10"] = df["close"] / g["close"].shift(10) * 100 - 100
    df["hi20"] = (df["close"] >= g["close"].transform(lambda s: s.rolling(20, min_periods=10).max()) - 1e-9)
    df["lim5"] = g["is_limit"].transform(lambda s: s.rolling(5, min_periods=1).sum().shift(1))
    df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))
    return df


def link_next(df):
    """给每个涨停日关联次日结果（是否连板 / 次日收益）。"""
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
        print(f"{title}: n=0")
        return
    hit = int(sub["hit"].sum())
    print(f"{title}: n={n:>5} 命中率 {hit/n*100:5.2f}% 均收 {sub['ret'].mean():+.2f}%")


def band_stats(m, col, edges, labels):
    print(f"\n── 按 {col} 分档 ──")
    for lo, hi, lab in zip(edges[:-1], edges[1:], labels):
        if lo is None:
            sub = m[m[col] < hi]
        elif hi is None:
            sub = m[m[col] >= lo]
        else:
            sub = m[(m[col] >= lo) & (m[col] < hi)]
        show(lab, sub)


def main():
    print("加载并重建涨停日历…")
    df = load_market()
    df = add_momentum(df)
    m = link_next(df)
    print(f"涨停样本: {len(m)}（含次日结果的涨停日）\n")

    # 视角1：全部涨停股（自然基准）
    print("=" * 70)
    print("视角1：全部涨停股（自然分布）")
    print("=" * 70)
    show("全样本", m)

    band_stats(m, "boards", [None, 2, 3, 4, 6, None],
               ["1板(首板)", "2板", "3板", "4-5板", "6板及以上"])

    # 当日涨停家数
    m["n_lim"] = m["date"].map(m.groupby("date").size())
    band_stats(m, "n_lim", [None, 40, 60, 80, 100, None],
               ["涨停<40家(冰点)", "40-60", "60-80", "80-100", "涨停≥100家(火爆)"])

    band_stats(m, "mom5", [None, 10, 20, 30, 50, None],
               ["5日动量<10%", "10-20%", "20-30%", "30-50%", "≥50%"])

    band_stats(m, "lim10", [None, 2, 3, 5, None],
               ["近10日涨停0-1次", "2次", "3-4次", "5次及以上"])

    show("20日新高", m[m["hi20"]])
    show("非20日新高", m[~m["hi20"]])

    print("\n" + "=" * 70)
    print("视角2：模拟模型 TOP1（每日按现评分规则打分取第1名）")
    print("=" * 70)
    # 复刻 backtest_baostock.score_day 的评分
    def score_day(pool):
        df = pool.copy()

        def board_score(b):
            return 10.0 if b >= 4 else {1: 6, 2: 8, 3: 9}.get(int(b), 6)
        df["s_board"] = df["boards"].apply(board_score)
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
        df["s_theme"] = 7.0
        df["score"] = (df["s_board"] * .25 + df["s_mood"] * .25 + df["s_pos"] * .25
                       + df["s_qual"] * .15 + df["s_theme"] * .10) * 10
        return df

    # 逐日打分取第1名（直接用 m 中的涨停行 + 加回原始 pct 全池）
    top1_rows = []
    for d, g in m.groupby("date"):
        # 需全池打分（m 已含全部涨停行 + 次日结果，评分只用当日信息，等效）
        scored = score_day(g).sort_values("score", ascending=False)
        top1_rows.append(scored.iloc[0])
    t1 = pd.DataFrame(top1_rows)
    show("模型 TOP1 整体", t1)
    show("  └ 其中 boards>=4", t1[t1["boards"] >= 4])
    show("  └ 其中 boards>=6", t1[t1["boards"] >= 6])
    show("  └ 其中 boards>=4 且 涨停≥60", t1[(t1["boards"] >= 4) & (t1["n_lim"] >= 60)])
    show("  └ 其中 boards>=4 且 涨停≥80", t1[(t1["boards"] >= 4) & (t1["n_lim"] >= 80)])
    show("  └ 其中 boards>=5", t1[t1["boards"] >= 5])
    show("  └ 其中 score>=80", t1[t1["score"] >= 80])
    show("  └ 其中 score>=85", t1[t1["score"] >= 85])
    show("  └ 其中 boards>=4 且 score>=85", t1[(t1["boards"] >= 4) & (t1["score"] >= 85)])
    show("  └ 其中 6板及以上 或 (5板且涨停≥80)", t1[(t1["boards"] >= 6) | ((t1["boards"] >= 5) & (t1["n_lim"] >= 80))])


if __name__ == "__main__":
    main()

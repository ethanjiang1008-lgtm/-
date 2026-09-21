# -*- coding: utf-8 -*-
"""v3 补充因子实验：20日新高、流通市值（由 amount/turn 倒推）对首板/低位池的提升。
用法：python v3_factors2.py <cache.csv>
"""
import sys
import pandas as pd

import explore_v3_factors as E

W_BOARD, W_LIM, W_MOM, W_TURN, W_VOL, W_MOOD = 0.30, 0.20, 0.15, 0.15, 0.10, 0.10


def add_factors2(m):
    """新增因子：f_new20（20日新高）、f_mktcap（流通市值分档）"""
    g = m.groupby("code", sort=False)
    # 20日新高（涨停日 close 为近20日最高）
    m["high20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=5).max())
    m["is_new20"] = m["close"] >= m["high20"] * 0.999
    # 流通市值（亿）= 成交额 / 换手率(%) * 100 / 1e8
    m["mktcap"] = m["amount"] / m["turn"].replace(0, pd.NA) * 100 / 1e8

    def _new20_s(x):
        return 10.0 if x else 5.0

    def _cap_s(x):
        if pd.isna(x): return 5.0
        if x < 30: return 10.0
        if x < 60: return 8.0
        if x < 100: return 7.0
        if x < 200: return 5.5
        return 4.0

    m["f_new20"] = m["is_new20"].apply(_new20_s)
    m["f_cap"] = m["mktcap"].apply(_cap_s)
    return m


def score8(df):
    return (df["f_board"] * W_BOARD + df["f_lim"] * W_LIM + df["f_mom"] * W_MOM
            + df["f_turn"] * W_TURN + df["f_vol"] * W_VOL + df["f_mood"] * W_MOOD
            + df["f_new20"] * 0.10 + df["f_cap"] * 0.10)


def hit_rate(df):
    if len(df) == 0:
        return 0.0, 0, 0
    return df["hit"].mean() * 100, int(df["hit"].sum()), len(df)


def run_top(df, top, split):
    picked = df.sort_values("score", ascending=False).groupby("date").head(top)
    o = hit_rate(picked)
    tr = hit_rate(picked[picked["date"] < split])
    va = hit_rate(picked[picked["date"] >= split])
    return o, tr, va  # 各为 (hr, hits, n)


def fmt(r):
    return f"全期 {r[0][0]:.2f}% (n={r[0][2]}) | 训练 {r[1][0]:.2f}% (n={r[1][2]}) / 验证 {r[2][0]:.2f}% (n={r[2][2]})"


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else "bs_daily_v3.csv.gz"
    m = E.link(E.load(cache))
    m = E.build_features(m)
    m = add_factors2(m)
    m["score"] = score8(m)
    SPLIT = E.SPLIT

    print("═══ 补充因子区分度 ═══")
    for name, mask in [
        ("全池基准", m["is_limit"]),
        ("20日新高涨停", m["is_limit"] & m["is_new20"]),
        ("非新高涨停", m["is_limit"] & ~m["is_new20"]),
        ("流通市值<30亿", m["is_limit"] & (m["mktcap"] < 30)),
        ("流通市值30-60亿", m["is_limit"] & (m["mktcap"] >= 30) & (m["mktcap"] < 60)),
        ("流通市值60-100亿", m["is_limit"] & (m["mktcap"] >= 60) & (m["mktcap"] < 100)),
        ("流通市值>200亿", m["is_limit"] & (m["mktcap"] >= 200)),
        ("首板+新高+市值<60亿", m["is_limit"] & (m["boards"] == 1) & m["is_new20"] & (m["mktcap"] < 60)),
    ]:
        r = hit_rate(m[mask])
        print(f"  {name}: 全期 {r[0]:.2f}% (n={r[2]})")

    # 首板池 8 因子 TOP1-5
    print("\n═══ 首板池 8因子 TOP1-5 ═══")
    fb = m[m["is_limit"] & (m["boards"] == 1)]
    for top in (1, 2, 3, 5):
        print(f"  TOP{top}: " + fmt(run_top(fb, top, SPLIT)))

    # 首板 + 新高 + 市值 筛精选池
    print("\n═══ 精选首板池（新高 + 市值<60亿 + 换手<5）TOP1-5 ═══")
    sel = fb[fb["is_new20"] & (m["mktcap"] < 60) & (m["turn"] < 5)]
    print(f"  候选样本: {len(sel)}（平均每天 {len(sel)/sel['date'].nunique():.1f} 只）")
    for top in (1, 2, 3):
        print(f"  TOP{top}: " + fmt(run_top(sel, top, SPLIT)))

    # 低位池 8 因子
    print("\n═══ 低位池 8因子 TOP1-5 ═══")
    low = m[m["is_limit"] & (m["boards"] <= 3)]
    for top in (1, 2, 3, 5):
        print(f"  TOP{top}: " + fmt(run_top(low, top, SPLIT)))


if __name__ == "__main__":
    main()

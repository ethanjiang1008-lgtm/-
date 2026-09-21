# -*- coding: utf-8 -*-
"""v3 完整回测：首板池 / 低位池 / 全池 × TOP1-5 命中率 + 概率校准。
用法：python v3_backtest.py <cache.csv> [rank]
rank: prob（默认，按次日连板概率取 TOP，与线上一致）| score（按综合分，旧口径对照）
"""
import sys
import pandas as pd

import explore_v3_factors as E
import model_v3 as MV

# 最优权重（网格搜索结果）
W_BOARD, W_LIM, W_MOM, W_TURN, W_VOL, W_MOOD = 0.30, 0.20, 0.15, 0.15, 0.10, 0.10
SPLIT = E.SPLIT


def score_row(df):
    """返回综合分（v3 六因子加权）"""
    return (df["f_board"] * W_BOARD + df["f_lim"] * W_LIM + df["f_mom"] * W_MOM
            + df["f_turn"] * W_TURN + df["f_vol"] * W_VOL + df["f_mood"] * W_MOOD)


def prob_row(df):
    """次日连板概率（分身位×综合分分位校准；历史场景无封单/事件增强）。
    与 model_v3._prob 一致，保证回测口径=线上口径。"""
    calib = MV.CALIB

    def _bucket(b):
        return int(b) if int(b) <= 3 else 4

    def _p(r):
        seg = calib.get(str(_bucket(int(r["boards"]))))
        if not seg:
            return float("nan")
        s = float(r["score"])
        best = seg[0]
        for q in seg:
            if s >= q["lo"]:
                best = q
        return best["rate"] * (1.0 + min(0.25, max(0.0, s - best["hi"]) / 10.0))

    return df.apply(_p, axis=1)


def hit_rate(df):
    if len(df) == 0:
        return 0.0, 0, 0
    return df["next_limit"].mean() * 100, int(df["next_limit"].sum()), len(df)


def run_pool(m, pool_name, pool_mask=None, tops=(1, 2, 3, 5), rank_col="prob"):
    """每天从池中按 rank_col（prob 概率 / score 综合分）取 TOPn，统计次日连板命中率。"""
    df = m[m["is_limit"]].copy()
    if pool_mask is not None:
        df = df[pool_mask]
    df = df.sort_values("date")
    results = {}
    for top in tops:
        if rank_col == "prob":
            # 主排序=概率，同分用综合分打破（与线上 score_pool_v3 一致）
            picked = df.groupby("date").apply(
                lambda g: g.sort_values(["prob", "score"], ascending=False).head(top),
                include_groups=False
            ).reset_index(level=0).rename(columns={"level_0": "date"})
        else:
            picked = df.groupby("date").apply(
                lambda g: g.nlargest(top, "score"), include_groups=False
            ).reset_index(level=0).rename(columns={"level_0": "date"})
        picked = picked.reset_index(drop=True)
        overall = hit_rate(picked)
        tr = hit_rate(picked[picked["date"] < SPLIT])
        va = hit_rate(picked[picked["date"] >= SPLIT])
        results[top] = (overall, tr, va)
    return results


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else "bs_daily_v3.csv.gz"
    rank = sys.argv[2] if len(sys.argv) > 2 else "prob"
    if rank not in ("prob", "score"):
        rank = "prob"
    m = E.link(E.load(cache))
    m = E.build_features(m)
    m["score"] = score_row(m)
    m["prob"] = prob_row(m)

    print(f"涨停样本 {len(m[m['is_limit']])}，交易日 {m[m['is_limit']]['date'].nunique()}")
    print(f"最优权重: 身位{W_BOARD} 频率{W_LIM} 动量{W_MOM} 换手{W_TURN} 放量{W_VOL} 情绪{W_MOOD}")
    print(f"切分点: {SPLIT}")
    print(f"排序口径: {'次日连板概率' if rank=='prob' else '综合分(旧口径)'}\n")

    low_mask = m["boards"] <= 3        # 低位池 1-3 板
    fb_mask = m["boards"] == 1         # 首板池
    high_mask = m["boards"] >= 4       # 高板池（对照）

    for name, mask in [("全池", None), ("低位池(1-3板)", low_mask), ("首板池", fb_mask), ("高板池(4板+)", high_mask)]:
        r = run_pool(m, name, mask, rank_col=rank)
        print(f"═══ {name} ═══")
        for top in (1, 2, 3, 5):
            o, tr, va = r[top]
            print(f"  TOP{top}: 全期 {o[0]:.2f}% (n={o[2]}) | 训练 {tr[0]:.2f}% (n={tr[2]}) / 验证 {va[0]:.2f}% (n={va[2]})")
        print()

    # 首板专项：分换手档
    print("═══ 首板 × 换手率分档（TOP1）═══")
    for lo, hi, label in [(0, 3, "<3"), (3, 5, "3-5"), (5, 10, "5-10"), (10, 100, "≥10")]:
        mask = fb_mask & m["turn"].between(lo, hi, inclusive="left")
        r = run_pool(m, "fb-turn", mask, tops=(1,), rank_col=rank)
        o, tr, va = r[1]
        print(f"  首板换手{label}: 全期 {o[0]:.2f}% (n={o[2]}) | 训练 {tr[0]:.2f}% / 验证 {va[0]:.2f}%")

    # 概率校准：分数分位 → 真实命中率
    print("\n═══ 概率校准（全池，按综合分分位）═══")
    df = m[m["is_limit"]].copy()
    df = df.sort_values("score")
    qs = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    labels = ["Q1(最低20%)", "Q2", "Q3", "Q4", "Q5(最高20%)"]
    for i in range(5):
        lo, hi = qs[i], qs[i + 1]
        seg = df.iloc[int(len(df) * lo):int(len(df) * hi)]
        hr, hits, n = hit_rate(seg)
        print(f"  {labels[i]}: 综合分[{seg['score'].min():.1f},{seg['score'].max():.1f}] 命中 {hr:.2f}% (n={n})")


if __name__ == "__main__":
    main()

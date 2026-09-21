# -*- coding: utf-8 -*-
"""回测结果分析：加载回测明细 CSV，产出核心指标报告与分档/分身位统计。

用法：python analyze_backtest.py --input bt_120d.csv [--baseline baseline.csv] [--out report.txt]
"""

import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="回测明细 CSV")
    ap.add_argument("--out", default="backtest_report.txt", help="报告输出路径")
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    valid = df[df["ret"].notna()].copy()
    n = len(valid)
    if n == 0:
        print("无有效记录")
        return

    lines = []
    lines.append("=" * 66)
    lines.append("首板连板概率模型 · 回测分析报告")
    lines.append(f"样本区间: {df['date'].min()} ~ {df['date'].max()}  共 {df['date'].nunique()} 个交易日")
    lines.append(f"有效交易: {n} 笔   (总记录 {len(df)} 笔)")
    lines.append("=" * 66)

    # 核心指标
    hit = int(valid["is_limit_up"].sum())
    win = int((valid["ret"] > 0).sum())
    avg = float(valid["ret"].mean())
    lines.append(f"\n【核心指标】")
    lines.append(f"  次日连板命中率: {hit}/{n} = {hit / n * 100:.2f}%")
    lines.append(f"  次日胜率(收益>0): {win}/{n} = {win / n * 100:.2f}%")
    lines.append(f"  平均次日收益: {avg:.2f}%")
    lines.append(f"  单笔最大盈利: {valid['ret'].max():.2f}%   单笔最大亏损: {valid['ret'].min():.2f}%")
    wins = valid[valid["ret"] > 0]["ret"]
    losses = valid[valid["ret"] <= 0]["ret"]
    pf = wins.sum() / abs(losses.sum()) if not losses.empty and losses.sum() != 0 else float("inf")
    lines.append(f"  盈亏比(Profit Factor): {pf if pf != float('inf') else 'inf':.2f}")

    # 按身位分档
    lines.append(f"\n【按当日连板身位分档】")
    for b in sorted(valid["boards"].unique()):
        sub = valid[valid["boards"] == b]
        h = int(sub["is_limit_up"].sum())
        lines.append(f"  {b}板: {len(sub)} 笔, 连板命中 {h/len(sub)*100:.1f}%, 平均收益 {sub['ret'].mean():.2f}%")

    # 按评级分档
    lines.append(f"\n【按模型评级分档】")
    for r in ["A+ 强预期", "A", "B", "C", "D"]:
        sub = valid[valid["rating"] == r]
        if sub.empty:
            continue
        h = int(sub["is_limit_up"].sum())
        lines.append(f"  {r}: {len(sub)} 笔, 连板命中 {h/len(sub)*100:.1f}%, 平均收益 {sub['ret'].mean():.2f}%")

    # 按概率分桶（检验概率校准）
    lines.append(f"\n【按模型概率分桶（校准检验）】")
    buckets = [(0.7, 0.85, "70-85%"), (0.6, 0.7, "60-70%"), (0.45, 0.6, "45-60%"),
               (0.35, 0.45, "35-45%"), (0.2, 0.35, "20-35%")]
    for lo, hi, label in buckets:
        sub = valid[(valid["prob"] >= lo) & (valid["prob"] < hi)]
        if sub.empty:
            continue
        h = int(sub["is_limit_up"].sum())
        lines.append(f"  {label}: {len(sub)} 笔, 实际连板率 {h/len(sub)*100:.1f}%")

    # 月度分布
    lines.append(f"\n【按月分布】")
    valid["month"] = valid["date"].str[:7]
    for m, sub in valid.groupby("month"):
        h = int(sub["is_limit_up"].sum())
        lines.append(f"  {m}: {len(sub)} 笔, 连板命中 {h/len(sub)*100:.1f}%, 平均收益 {sub['ret'].mean():+.2f}%")

    text = "\n".join(lines)
    print(text)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()

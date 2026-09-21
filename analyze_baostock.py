# -*- coding: utf-8 -*-
"""baostock 1年回测深析：TopN 敏感性、概率分桶校准、月度稳定性、身位分档。
用法：python analyze_baostock.py --input backtest_baostock.csv
"""

import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="backtest_baostock.csv")
    ap.add_argument("--out", default="backtest_report_bs.txt")
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    valid = df[df["ret"].notna()].copy()
    n = len(valid)
    lines = []
    lines.append("=" * 66)
    lines.append("baostock 长周期回测 · 深度分析")
    lines.append(f"样本区间: {valid['date'].min()} ~ {valid['date'].max()}  "
                 f"共 {valid['date'].nunique()} 个交易日, 有效交易 {n} 笔")
    lines.append("=" * 66)

    def stats(sub):
        nn = len(sub)
        if nn == 0:
            return None
        hit = int(sub["is_limit_up"].sum())
        win = int((sub["ret"] > 0).sum())
        avg = float(sub["ret"].mean())
        w = sub[sub["ret"] > 0]["ret"].sum()
        l = abs(sub[sub["ret"] <= 0]["ret"].sum())
        pf = w / l if l else float("inf")
        return dict(n=nn, hit_rate=round(hit / nn * 100, 1),
                    avg_ret=round(avg, 2), win_rate=round(win / nn * 100, 1),
                    pf=round(pf, 2) if pf != float("inf") else None)

    # 整体
    s = stats(valid)
    lines.append(f"\n【整体】命中率 {s['hit_rate']}% | 平均收益 {s['avg_ret']}% | "
                 f"胜率 {s['win_rate']}% | 盈亏比 {s['pf']} | 交易 {s['n']} 笔")

    # 按月
    lines.append("\n【月度稳定性】")
    valid["month"] = valid["date"].str[:7]
    for m, sub in valid.groupby("month"):
        ss = stats(sub)
        lines.append(f"  {m}: 交易 {ss['n']:>3} 笔 | 命中率 {ss['hit_rate']:>5}% | "
                     f"平均收益 {ss['avg_ret']:+.2f}% | 胜率 {ss['win_rate']:>5}%")

    # 按身位
    lines.append("\n【按当日连板身位】")
    for b in sorted(valid["boards"].unique()):
        sub = valid[valid["boards"] == b]
        ss = stats(sub)
        lines.append(f"  {b}板: 交易 {ss['n']:>3} 笔 | 命中率 {ss['hit_rate']:>5}% | "
                     f"平均收益 {ss['avg_ret']:+.2f}% | 胜率 {ss['win_rate']:>5}%")

    # 评分分布
    lines.append("\n【评分区间表现】")
    for lo, hi in [(80, 101), (70, 80), (60, 70), (0, 60)]:
        sub = valid[(valid["score"] >= lo) & (valid["score"] < hi)]
        if sub.empty:
            continue
        ss = stats(sub)
        lines.append(f"  {lo}-{hi}分: 交易 {ss['n']:>3} 笔 | 命中率 {ss['hit_rate']:>5}% | "
                     f"平均收益 {ss['avg_ret']:+.2f}%")

    # 连板股 vs 首板股
    lines.append("\n【首板 vs 连板】")
    for tag, mask in [("首板(boards=1)", valid["boards"] == 1),
                      ("连板(boards>=2)", valid["boards"] >= 2)]:
        sub = valid[mask]
        ss = stats(sub)
        lines.append(f"  {tag}: 交易 {ss['n']:>3} 笔 | 命中率 {ss['hit_rate']:>5}% | "
                     f"平均收益 {ss['avg_ret']:+.2f}% | 胜率 {ss['win_rate']:>5}%")

    text = "\n".join(lines)
    print(text)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()

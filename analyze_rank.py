# -*- coding: utf-8 -*-
"""计算 TOP1-TOP5 各自命中率：每天去重后按 score 排序取前5，统计每个名次的次日连板命中率。"""
import pandas as pd


def analyze(path, label):
    df = pd.read_csv(path, dtype={"code": str})
    # 同一天同一股票可能因身位偏差出现两行，取 score 最高的一行（buy/ret 相同）
    df = df.sort_values(["date", "code", "score"], ascending=[True, True, False])
    df = df.drop_duplicates(["date", "code"], keep="first").reset_index(drop=True)
    # 每天按 score 降序排名（同分按代码稳定排序）
    df["rank"] = df.groupby("date")["score"].rank(
        method="first", ascending=False).astype(int)
    df = df[df["rank"] <= 5]

    print("=" * 64)
    print(f"{label}")
    print("=" * 64)
    print(f"{'名次':<4}{'笔数':>6}{'命中率':>9}{'平均收益':>10}{'胜率':>8}")
    print("-" * 44)
    total_hit = total_n = 0
    for r in range(1, 6):
        sub = df[df["rank"] == r]
        n = len(sub)
        if n == 0:
            print(f"{r}     0  （无记录）")
            continue
        hit = int(sub["is_limit_up"].sum())
        win = int((sub["ret"] > 0).sum())
        print(f"{r}   {n:>6}{hit/n*100:>8.2f}%{sub['ret'].mean():>9.2f}%{win/n*100:>7.2f}%")
        total_hit += hit
        total_n += n
    print("-" * 44)
    print(f"合计  {total_n:>6}{total_hit/total_n*100:>8.2f}%  （每日去重后全部入选股票）")
    # 每日实际选入只数分布
    cnt = df.groupby("date").size()
    print(f"每日选入只数分布: {cnt.value_counts().sort_index().to_dict()}")
    return df


if __name__ == "__main__":
    print(">>> 全池 1 年回测（2025-06-02 ~ 2026-09-18）")
    d1 = analyze("backtest_baostock_all.csv", "全池模型 Top1-5")
    print()
    print(">>> 首板专项 1 年回测")
    d2 = analyze("backtest_baostock_fb.csv", "首板专项模型 Top1-5")
    d1.to_csv("rank_stats_all.csv", index=False, encoding="utf-8-sig")
    d2.to_csv("rank_stats_fb.csv", index=False, encoding="utf-8-sig")

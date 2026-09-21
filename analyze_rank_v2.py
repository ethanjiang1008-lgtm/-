# -*- coding: utf-8 -*-
"""TOP1/TOP2/TOP3 各自命中率分析（v2）。输入 backtest --top-n 3 的 CSV，
按日期分组，第 1/2/3 行分别为当日第 1/2/3 名，分别统计命中率。"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

SCEN = [
    ("全池 v2", "bt_v2_top3.csv"),
    ("首板专项", "bt_v2_fb_top3.csv"),
    ("低位(1-3板)", "bt_v2_low3_top3.csv"),
    ("低位精准(恰好3板)", "bt_v2_low3_eq3_top3.csv"),
]

for name, f in SCEN:
    try:
        df = pd.read_csv(f, dtype={"code": str})
    except FileNotFoundError:
        print(f"{name}: 文件不存在 {f}")
        continue
    df["is_limit_up"] = df["is_limit_up"].astype(bool)
    df["rank"] = df.groupby("date").cumcount() + 1
    print(f"\n===== {name}（{len(df)} 笔）=====")
    for rk in (1, 2, 3):
        sub = df[df["rank"] == rk]
        if sub.empty:
            print(f"  TOP{rk}: 无样本")
            continue
        hit = sub["is_limit_up"].mean() * 100
        tr = sub[sub["date"] < "2026-03-01"]
        va = sub[sub["date"] >= "2026-03-01"]
        print(f"  TOP{rk}: n={len(sub):>4} 全期 {hit:5.2f}% | "
              f"训练 {tr['is_limit_up'].mean()*100:5.2f}%({len(tr)}) / "
              f"验证 {va['is_limit_up'].mean()*100:5.2f}%({len(va)}) | "
              f"均收 {sub['ret'].mean():+.2f}% 胜率 {(sub['ret']>0).mean()*100:.1f}%")

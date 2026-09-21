# -*- coding: utf-8 -*-
"""v2 分段验证：把 1 年回测按 前2/3（2025-06~2026-02，训练）/ 后1/3（2026-03~09，验证）
分开统计命中率，确认策略不是靠全期均值撑起来的（防止过拟合与市场环境依赖）。"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

SPLIT = "2026-03-01"
FILES = {
    "全池 TOP1+身位≥6": "bt_v2_top1_g6.csv",
    "全池 TOP5": "bt_v2_top5.csv",
    "首板 TOP1": "bt_v2_fb_top1.csv",
    "首板 TOP5": "bt_v2_fb.csv",
}


def stats(df, label):
    n = len(df)
    if n == 0:
        print(f"  {label}: n=0")
        return
    hit = int(df["is_limit_up"].sum())
    print(f"  {label}: n={n:>4} 命中率 {hit/n*100:5.2f}%  均收 {df['ret'].mean():+.2f}%  "
          f"胜率 {(df['ret']>0).mean()*100:.1f}%")


def main():
    for name, f in FILES.items():
        df = pd.read_csv(f, dtype={"code": str})
        df["is_limit_up"] = df["is_limit_up"].astype(bool)
        print(f"═══ {name}（{f}）═══")
        stats(df, "全期")
        tr = df[df["date"] < SPLIT]
        va = df[df["date"] >= SPLIT]
        stats(tr, f"训练段 {tr['date'].min()}~{tr['date'].max()}（{tr['date'].nunique()}个交易日）")
        stats(va, f"验证段 {va['date'].min()}~{va['date'].max()}（{va['date'].nunique()}个交易日）")
        # 按身位拆（全池模式）
        if name.startswith("全池"):
            print("  ── 按身位（全期）──")
            for b, g in df.groupby("boards"):
                stats(g, f"{int(b)}板")
        print()


if __name__ == "__main__":
    main()

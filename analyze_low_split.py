# -*- coding: utf-8 -*-
"""低位模式分段验证：前 2/3 训练 / 后 1/3 验证。"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

SPLIT = "2026-03-01"
FILES = [
    ("低位 Top1（1-3板）", "bt_v2_low3.csv"),
    ("低位精准 Top1（恰好3板）", "bt_v2_low3_eq3.csv"),
]

for name, f in FILES:
    df = pd.read_csv(f, dtype={"code": str})
    df["is_limit_up"] = df["is_limit_up"].astype(bool)
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    all_hit = df["is_limit_up"].mean() * 100
    tr_hit = tr["is_limit_up"].mean() * 100
    va_hit = va["is_limit_up"].mean() * 100
    tr_ret = tr["ret"].mean()
    va_ret = va["ret"].mean()
    print(f"{name}: 全期 {all_hit:.2f}% ({len(df)}笔) | "
          f"训练 {tr_hit:.2f}% ({len(tr)}笔, 均收{tr_ret:+.2f}%) | "
          f"验证 {va_hit:.2f}% ({len(va)}笔, 均收{va_ret:+.2f}%)")

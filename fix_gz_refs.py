# -*- coding: utf-8 -*-
"""把 v3 脚本中 bs_daily_v3.csv 引用改为 .gz（文本级替换）。"""
import re

FILES = [
    "explore_v3_factors.py", "make_calib.py", "patch_v3_today.py",
    "v3_backtest.py", "v3_factors2.py", "merge_v3.py", "data_baostock_v3.py",
]
for f in FILES:
    s = open(f, encoding="utf-8").read()
    s2 = s.replace('"bs_daily_v3.csv"', '"bs_daily_v3.csv.gz"')
    s2 = s2.replace("bs_daily_v3.csv.gz.gz", "bs_daily_v3.csv.gz")
    s2 = s2.replace("bs_daily_v3.csv (含", "bs_daily_v3.csv.gz（含")
    if s2 != s:
        open(f, "w", encoding="utf-8").write(s2)
        print(f"{f}: updated")
    else:
        print(f"{f}: no change")

# patch_v3_today.py: 合并写回需要 gzip 压缩
s = open("patch_v3_today.py", encoding="utf-8").read()
s = s.replace(
    'merged.to_csv(CACHE, index=False, encoding="utf-8-sig")',
    'merged.to_csv(CACHE, index=False, encoding="utf-8-sig", compression="gzip")')
open("patch_v3_today.py", "w", encoding="utf-8").write(s)
print("patch_v3_today.py: to_csv gzip")

# merge_v3.py: 输出 .gz
s = open("merge_v3.py", encoding="utf-8").read()
s = s.replace(
    'merged.to_csv("bs_daily_v3.csv.gz", index=False, encoding="utf-8-sig")',
    'merged.to_csv("bs_daily_v3.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")')
s = s.replace(
    'merged.to_csv("bs_daily_v3.csv", index=False, encoding="utf-8-sig")',
    'merged.to_csv("bs_daily_v3.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")')
open("merge_v3.py", "w", encoding="utf-8").write(s)
print("merge_v3.py: to_csv gzip")

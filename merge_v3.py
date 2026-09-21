# -*- coding: utf-8 -*-
"""合并 bs_v3_part*.csv + 种子 bs_daily_v3_new.csv → bs_daily_v3.csv，去重验证。"""
import pandas as pd

parts = []
for f in ["bs_daily_v3_new.csv", "bs_v3_part0.csv", "bs_v3_part1.csv", "bs_v3_part2.csv"]:
    try:
        df = pd.read_csv(f, dtype={"code": str})
        parts.append(df)
        print(f"{f}: {len(df)} 行 / {df['code'].nunique()} 只")
    except Exception as e:
        print(f"{f} 读取失败: {e}")

merged = pd.concat(parts, ignore_index=True)
merged = merged.drop_duplicates(subset=["code", "date"]).sort_values(["code", "date"])
merged.to_csv("bs_daily_v3.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")
print(f"\n合并完成: {len(merged)} 行 / {merged['code'].nunique()} 只")
print(f"日期: {merged['date'].min()} ~ {merged['date'].max()}")
print(f"换手率缺失: {merged['turn'].isna().mean()*100:.2f}%")
print(f"成交额缺失: {merged['amount'].isna().mean()*100:.2f}%")
print(f"成交量缺失: {merged['volume'].isna().mean()*100:.2f}%")

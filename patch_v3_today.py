# -*- coding: utf-8 -*-
"""补拉指定日期（默认今天）涨停池股票的日线，合并进 bs_daily_v3.csv。
用法：python patch_v3_today.py [YYYY-MM-DD]
"""
import sys
import time

import pandas as pd

import data_baostock_v3 as V3
import data_fetcher as F

CACHE = "bs_daily_v3.csv.gz"


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else F.recent_trade_dates(n=1)[-1]
    pool = F.limit_up_pool(date)
    codes = [str(c).strip().zfill(6) for c in pool["代码"]]
    print(f"补拉 {date} 涨停池 {len(codes)} 只")

    import baostock as bs
    lg = bs.login()
    assert lg.error_code == "0", lg.error_msg

    rows = []
    failed = []
    for i, code in enumerate(codes):
        try:
            _, rs = V3._query_one(code, "2026-09-14", date)
            rows.extend(rs)
        except Exception:
            failed.append(code)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(codes)}")
        time.sleep(0.05)

    old = pd.read_csv(CACHE, dtype={"code": str})
    new = pd.DataFrame(rows, columns=["code", "date", "close", "pct", "is_st",
                                      "volume", "amount", "turn"])
    merged = pd.concat([old, new], ignore_index=True)
    merged = merged.drop_duplicates(subset=["code", "date"]).sort_values(["code", "date"])
    merged.to_csv(CACHE, index=False, encoding="utf-8-sig", compression="gzip")
    print(f"合并完成: {len(merged)} 行（+{len(rows)}），失败 {len(failed)}: {failed[:10]}")
    print(f"日期覆盖: {merged['date'].min()} ~ {merged['date'].max()}")


if __name__ == "__main__":
    main()

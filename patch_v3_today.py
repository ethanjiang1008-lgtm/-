# -*- coding: utf-8 -*-
"""补拉指定日期（默认最近交易日）涨停池股票的日线，合并进 bs_daily_v3.csv.gz。

数据源策略（解决"当日数据延迟"问题）：
1) 优先 baostock 历史日线（覆盖历史段，稳定）。
2) 若 baostock 未返回 target 日数据（T 日数据通常收盘后数小时才更新），
   回退用「东方财富涨停池」当日字段构造 target 日行：
      close=最新价  pct=涨跌幅  amount=成交额  turn=换手率  volume=成交额/close
      is_st=名称含ST   boards 存连板数（不入缓存列，供校验）
   涨停池覆盖的正是"当日涨停股"——即当日预测对象，非涨停股缺当日行不影响预测。

用法：python patch_v3_today.py [YYYY-MM-DD]
"""
import sys
import time

import pandas as pd

import data_baostock_v3 as V3
import data_fetcher as F

CACHE = "bs_daily_v3.csv.gz"


def _st_flag(name: str) -> bool:
    n = str(name or "").upper()
    return "ST" in n


def _fallback_rows_from_ztpool(date: str) -> tuple[list, list]:
    """用东财涨停池构造当日行。返回 (rows, used_fields)。"""
    pool = F.limit_up_pool(date)
    rows = []
    used = 0
    for _, r in pool.iterrows():
        code = str(r["代码"]).strip().zfill(6)
        try:
            close = float(r["最新价"])
            pct = float(r["涨跌幅"])
            amt = float(r["成交额"])
            turn = float(r["换手率"])
        except Exception:
            continue
        vol = amt / close if close else 0.0
        rows.append((code, date, close, pct, _st_flag(r.get("名称")),
                     vol, amt, turn))
        used += 1
    return rows, used


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else F.recent_trade_dates(n=1)[-1]
    pool = F.limit_up_pool(date)
    codes = [str(c).strip().zfill(6) for c in pool["代码"]]
    print(f"补拉 {date} 涨停池 {len(codes)} 只")

    import baostock as bs
    lg = bs.login()
    assert lg.error_code == "0", lg.error_msg

    # 历史段起点（覆盖 mom5/lim10 所需窗口）
    start = "2026-09-14"

    rows = []
    failed = []
    for i, code in enumerate(codes):
        try:
            _, rs = V3._query_one(code, start, date)
            rows.extend(rs)
        except Exception:
            failed.append(code)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(codes)}")
        time.sleep(0.05)

    # 检查 target 日是否已覆盖；没有则用涨停池当日字段回退
    has_target = any(r[1] == date for r in rows)
    if has_target:
        print(f"baostock 已覆盖 {date}（{sum(1 for r in rows if r[1] == date)} 行）")
    else:
        fb_rows, used = _fallback_rows_from_ztpool(date)
        print(f"baostock 无 {date} 数据 → 用东财涨停池构造 {used} 行当日行情")
        # 去掉 baostock 拉到但缺 target 的历史重复行交给 dedup
        rows = rows + fb_rows

    old = pd.read_csv(CACHE, dtype={"code": str})
    new = pd.DataFrame(rows, columns=["code", "date", "close", "pct", "is_st",
                                      "volume", "amount", "turn"])
    merged = pd.concat([old, new], ignore_index=True)
    merged = merged.drop_duplicates(subset=["code", "date"]).sort_values(["code", "date"])
    merged.to_csv(CACHE, index=False, encoding="utf-8-sig", compression="gzip")
    n_target = int((merged["date"] == date).sum())
    print(f"合并完成: {len(merged)} 行（新增 {len(rows)}），失败 {len(failed)}: {failed[:10]}")
    print(f"日期覆盖: {merged['date'].min()} ~ {merged['date'].max()}；{date} 共 {n_target} 行")
    if n_target == 0:
        print("!! WARN: target 日仍无数据，后续 run_daily_v3 将回退或失败")
        sys.exit(2)


if __name__ == "__main__":
    main()

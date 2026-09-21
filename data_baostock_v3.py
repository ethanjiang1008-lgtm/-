# -*- coding: utf-8 -*-
"""baostock 数据层 v3：在 v2 基础上扩展量能字段（volume/amount/turn），
支持断点续传。输出新缓存 bs_daily_v3.csv，列：code,date,close,pct,is_st,volume,amount,turn
"""

import os
import time
import pandas as pd
import baostock as bs

import data_baostock as D

_logged_in = False


def _login():
    global _logged_in
    if not _logged_in:
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        _logged_in = True


def _query_one(code: str, start: str, end: str, retries: int = 3):
    """返回 (code, [(code, date, close, pct, is_st, volume, amount, turn), ...])
    带失败重试。"""
    for attempt in range(retries):
        try:
            rows = []
            rs = bs.query_history_k_data_plus(
                D._bs_code(code), "date,close,pctChg,isST,volume,amount,turn",
                start_date=start, end_date=end,
                frequency="d", adjustflag="3")
            while rs.next():
                r = rs.get_row_data()
                rows.append((code, r[0],
                             float(r[1] or 0), float(r[2] or 0), r[3] == "1",
                             float(r[4] or 0), float(r[5] or 0), float(r[6] or 0)))
            return code, rows
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.0)
    return code, []


def fetch_all_daily_v3(start: str, end: str, cache: str = "bs_daily_v3.csv.gz",
                       batch: int = 300, progress_every: int = 300) -> pd.DataFrame:
    """逐股拉 start~end 日线（含量能），断点续传式落盘。"""
    _login()
    codes = D.all_codes(day=end)

    done_codes = set()
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        try:
            existing = pd.read_csv(cache, dtype={"code": str})
            done_codes = set(existing["code"].unique())
            print(f"已有缓存 {cache}：{len(done_codes)} 只已完成，跳过")
        except Exception:
            pass

    todo = [c for c in codes if c not in done_codes]
    if not todo:
        print("全部股票已在缓存中")
        return pd.read_csv(cache, dtype={"code": str})

    failed = []
    t0 = time.time()
    batch_rows = []
    written = 0
    for i, code in enumerate(todo):
        if (i + 1) % progress_every == 0:
            el = time.time() - t0
            print(f"  进度 {i + 1}/{len(todo)} 只，用时 {el:.0f}s…")
        try:
            _, rows = _query_one(code, start, end)
            if rows:
                batch_rows.extend(rows)   # rows 已含 code 列
        except Exception:
            failed.append(code)
        if i % 100 == 0:
            time.sleep(0.15)
        if batch_rows and (i + 1) % batch == 0:
            _append(cache, batch_rows)
            written += len(batch_rows)
            batch_rows = []
            print(f"  → 已落盘 {written} 行，剩余 {len(todo) - i - 1} 只")
    if batch_rows:
        _append(cache, batch_rows)
        written += len(batch_rows)

    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        df = pd.read_csv(cache, dtype={"code": str})
    else:
        df = pd.DataFrame(columns=["code", "date", "close", "pct", "is_st",
                                   "volume", "amount", "turn"])
    if failed:
        print(f"  [warn] {len(failed)} 只拉取失败: {failed[:10]}")
    print(f"拉取完成：{len(df)} 行（{df['code'].nunique()} 只），用时 {time.time()-t0:.0f}s")
    return df


def _append(cache: str, rows: list):
    import csv
    first = not (os.path.exists(cache) and os.path.getsize(cache) > 0)
    with open(cache, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if first:
            w.writerow(["code", "date", "close", "pct", "is_st", "volume", "amount", "turn"])
        w.writerows(rows)


if __name__ == "__main__":
    fetch_all_daily_v3("2025-06-02", "2026-09-18")

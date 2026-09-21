# -*- coding: utf-8 -*-
"""补拉剩余股票：带单次查询超时保护，完成 baostock 全市场日线缓存。"""
import threading
import time
import pandas as pd
import baostock as bs
import data_baostock as DB

CACHE = "bs_daily_all.csv"


def query_with_timeout(code, start, end, timeout=15):
    """带超时的单股查询。超时返回 None。"""
    result = {}

    def worker():
        try:
            _, rows = DB._query_one(code, start, end)
            result["rows"] = rows
        except Exception as e:
            result["err"] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None  # 超时
    return result.get("rows", [])


def main():
    bs.login()
    start, end = "2025-06-02", "2026-09-18"
    codes = DB.all_codes(day=end)

    existing = pd.read_csv(CACHE, dtype={"code": str})
    done = set(existing["code"].unique())
    todo = [c for c in codes if c not in done]
    print(f"缓存已有 {len(done)} 只，待补拉 {len(todo)} 只")

    failed, timedout = [], 0
    new_rows = []
    t0 = time.time()
    for i, code in enumerate(todo):
        rows = query_with_timeout(code, start, end, timeout=12)
        if rows is None:
            timedout += 1
            failed.append(code)
            print(f"  [{i+1}/{len(todo)}] {code} 超时，跳过")
            continue
        if rows:
            new_rows.extend((code, d, c, p, s) for d, c, p, s in rows)
        if (i + 1) % 50 == 0:
            print(f"  进度 {i+1}/{len(todo)}，新增 {len(new_rows)} 行，用时 {time.time()-t0:.0f}s")
        time.sleep(0.05)

    if new_rows:
        DB._append_cache(CACHE, new_rows)
        print(f"追加 {len(new_rows)} 行")
    final = pd.read_csv(CACHE, dtype={"code": str})
    print(f"完成：缓存现有 {final['code'].nunique()} 只 / {len(final)} 行")
    print(f"失败/超时 {len(failed)} 只: {failed[:20]}")
    bs.logout()


if __name__ == "__main__":
    main()

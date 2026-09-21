# -*- coding: utf-8 -*-
"""并行拉取全市场日线（含量能字段）：3 进程各拉一段，各自续传，最后合并。
用法：python multi_fetch.py
"""
import os
import sys
import time

import pandas as pd

import data_baostock as D
import data_baostock_v3 as V3

SEG = 3
START, END = "2025-06-02", "2026-09-18"
SEED = "bs_daily_v3_new.csv"          # 已拉部分（600 只）
OUT_PREFIX = "bs_v3_part"             # part 文件前缀


def worker(seg_id, codes, start, end, part_file):
    """单进程拉取一段，断点续传。"""
    import baostock as bs
    lg = bs.login()
    if lg.error_code != "0":
        print(f"[seg{seg_id}] login failed: {lg.error_msg}")
        return
    done = set()
    if os.path.exists(part_file) and os.path.getsize(part_file) > 0:
        try:
            done = set(pd.read_csv(part_file, dtype={"code": str})["code"].unique())
            print(f"[seg{seg_id}] 已有 {len(done)} 只，跳过")
        except Exception:
            pass
    todo = [c for c in codes if c not in done]
    t0 = time.time()
    rows_buf = []
    failed = []
    for i, code in enumerate(todo):
        if (i + 1) % 100 == 0:
            print(f"[seg{seg_id}] {i + 1}/{len(todo)} 用时 {time.time()-t0:.0f}s")
        try:
            _, rows = V3._query_one(code, start, end)
            if rows:
                rows_buf.extend(rows)
        except Exception:
            failed.append(code)
        if rows_buf and (i + 1) % 200 == 0:
            _append(part_file, rows_buf)
            rows_buf = []
    if rows_buf:
        _append(part_file, rows_buf)
    print(f"[seg{seg_id}] 完成：{len(todo)} 只，失败 {len(failed[:10])}：{failed[:10]}")


def _append(path: str, rows: list):
    import csv
    first = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if first:
            w.writerow(["code", "date", "close", "pct", "is_st", "volume", "amount", "turn"])
        w.writerows(rows)


def main():
    import multiprocessing as mp
    codes = D.all_codes(day=END)
    # 排除种子文件已完成的
    seed_done = set()
    if os.path.exists(SEED) and os.path.getsize(SEED) > 0:
        seed_done = set(pd.read_csv(SEED, dtype={"code": str})["code"].unique())
        print(f"种子已有 {len(seed_done)} 只")
    todo = [c for c in codes if c not in seed_done]
    print(f"待拉 {len(todo)} 只，分 {SEG} 段并行")
    segs = [[] for _ in range(SEG)]
    for i, c in enumerate(todo):
        segs[i % SEG].append(c)
    procs = []
    for s in range(SEG):
        p = mp.Process(target=worker, args=(s, segs[s], START, END, f"{OUT_PREFIX}{s}.csv"))
        p.start()
        procs.append(p)
    for p in procs:
        p.join()
    print("ALL SEGS DONE")


if __name__ == "__main__":
    main()

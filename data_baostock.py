# -*- coding: utf-8 -*-
"""baostock 数据层 v2：全市场全历史日线 → 本地构建涨停日历 + 全市场价格表。
支持断点续传：每批拉取即追加落盘，中断后自动从已有缓存继续，不重复拉取。
"""

import os
import time
import pandas as pd
import baostock as bs

_logged_in = False


def _login():
    global _logged_in
    if not _logged_in:
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        _logged_in = True


# ── 全市场股票列表 ──────────────────────────────────────

def all_codes(day: str = None) -> list[str]:
    """全部 A 股代码（纯 6 位）。day 用查询日（默认今天）。"""
    _login()
    rs = bs.query_all_stock(day=day)
    codes = []
    while rs.next():
        row = rs.get_row_data()
        code = row[0].split(".")[1]
        codes.append(code)
    return codes


# ── 全市场日线（断点续传式拉取）────────────────────────

def _bs_code(c: str) -> str:
    if c.startswith(("6", "9")):
        return f"sh.{c}"
    return f"sz.{c}"


def _query_one(code: str, start: str, end: str):
    """返回单只股票 (code, [(date, close, pct, is_st), ...])"""
    rows = []
    rs = bs.query_history_k_data_plus(
        _bs_code(code), "date,close,pctChg,isST",
        start_date=start, end_date=end,
        frequency="d", adjustflag="3")
    while rs.next():
        r = rs.get_row_data()
        rows.append((r[0], float(r[1] or 0), float(r[2] or 0), r[3] == "1"))
    return code, rows


def fetch_all_daily(start: str, end: str, codes: list[str] = None,
                    progress_every: int = 300, cache: str = "bs_daily_all.csv",
                    batch: int = 300) -> pd.DataFrame:
    """逐股拉 start~end 日线，返回 DataFrame：code, date, close, pct, is_st。
    支持断点续传：已存在于 cache 中的 code 自动跳过，每 batch 只追加落盘一次。
    """
    _login()
    if codes is None:
        codes = all_codes(day=end)

    # 读已有缓存，得到已完成的 code 集合
    done_codes = set()
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        try:
            existing = pd.read_csv(cache, dtype={"code": str})
            done_codes = set(existing["code"].unique())
            print(f"检测到已有缓存 {cache}：{len(done_codes)} 只已完成，跳过")
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
            print(f"  进度 {i + 1}/{len(todo)} 只（共 {len(codes)}），用时 {el:.0f}s…")
        try:
            _, rows = _query_one(code, start, end)
            if rows:
                batch_rows.extend((code, d, c, p, s) for d, c, p, s in rows)
        except Exception:
            failed.append(code)
        # 限速：每 100 只 0.2s（比之前更快）
        if i % 100 == 0:
            time.sleep(0.2)
        # 每 batch 只追加落盘
        if batch_rows and (i + 1) % batch == 0:
            _append_cache(cache, batch_rows)
            written += len(batch_rows)
            batch_rows = []
            print(f"  → 已落盘 {written} 行，剩余 {len(todo) - i - 1} 只")
    if batch_rows:
        _append_cache(cache, batch_rows)
        written += len(batch_rows)

    # 合并最终结果
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        df = pd.read_csv(cache, dtype={"code": str})
    else:
        df = pd.DataFrame(columns=["code", "date", "close", "pct", "is_st"])
    if failed:
        print(f"  [warn] {len(failed)} 只股票拉取失败: {failed[:10]}")
    print(f"拉取完成：{len(df)} 行日线（{df['code'].nunique()} 只），用时 {time.time()-t0:.0f}s")
    return df


def _append_cache(cache: str, rows: list):
    """追加写入缓存（无表头），原子性由单进程保证。"""
    import csv
    first = not (os.path.exists(cache) and os.path.getsize(cache) > 0)
    with open(cache, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if first:
            w.writerow(["code", "date", "close", "pct", "is_st"])
        w.writerows(rows)


# ── 从日线构建涨停日历与价格表 ─────────────────────────

def build_market(start: str, end: str, codes: list[str] = None) -> tuple:
    """返回 (limit_up_dict, price_dict, trade_dates)。
    limit_up_dict: {date: DataFrame(code, boards, close, pct)}
    price_dict:    {code: DataFrame(date, close)}   全市场收盘价
    trade_dates:   sorted 交易日列表
    """
    df = fetch_all_daily(start, end, codes)
    if df.empty:
        return {}, {}, []

    df = df.sort_values(["code", "date"]).reset_index(drop=True)

    # 涨停判定：主板 9.8 / 创业板科创(3,68) 19.8 / ST 主板 4.8 / ST 创业 9.8
    def thresh(row):
        if row["is_st"]:
            return 9.8 if row["code"].startswith(("3", "68")) else 4.8
        return 19.8 if row["code"].startswith(("3", "68")) else 9.8

    df["thresh"] = df.apply(thresh, axis=1)
    df["is_limit"] = df["pct"] >= df["thresh"] - 1e-6

    # 向量化连板计数：非涨停日作为分组边界重置
    df["_grp"] = (~df["is_limit"]).groupby(df["code"]).cumsum()
    df["boards"] = df.groupby(["code", "_grp"])["is_limit"].cumsum().astype(int)
    df = df.drop(columns=["_grp"])

    # 涨停日历
    lim = df[df["is_limit"]]
    cal = {}
    for d, g in lim.groupby("date"):
        cal[d] = g[["code", "boards", "close", "pct"]].reset_index(drop=True)

    # 全市场价格表（供次日收益/连板判定）
    price = {}
    for code, g in df.groupby("code"):
        price[code] = g[["date", "close", "pct"]].reset_index(drop=True)

    trade_dates = sorted(df["date"].unique())
    return cal, price, trade_dates


def bs_trade_dates(start: str, end: str) -> list[str]:
    _login()
    rs = bs.query_trade_dates(start_date=start, end_date=end)
    out = []
    while rs.next():
        row = rs.get_row_data()
        if row[1] == "1":
            out.append(row[0])
    return sorted(out)

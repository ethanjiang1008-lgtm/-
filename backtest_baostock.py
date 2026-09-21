# -*- coding: utf-8 -*-
"""baostock 长周期回测 v2：全市场日线一次性拉取 → 本地构建涨停日历与价格表
→ 逐日打分选股 → 尾盘买入（涨停收盘价）→ 次日判定连板/收益。

回测区间可任意设置（如近 1 年 250 交易日），不受涨停池接口近端限制。
简化因子（baostock 无封板时间/炸板次数/封板资金）：
  连板身位25% + 市场情绪25% + 个股身位25% + 封板质量15% + 题材强度10%(中性)
"""

import argparse
import os
import time
import pandas as pd

import data_baostock as DB

# 缓存文件：拉取一次全市场日线后落盘，后续直接读
DAILY_CACHE = "bs_daily_all.csv"


# ── 数据获取（带缓存）───────────────────────────────────

def get_market(start: str, end: str, force: bool = False) -> tuple:
    """返回 (limit_up_dict, price_dict, trade_dates)。"""
    if not force and os.path.exists(DAILY_CACHE):
        t0 = time.time()
        df = pd.read_csv(DAILY_CACHE, dtype={"code": str})
        # 从缓存重建
        df = df.sort_values(["code", "date"]).reset_index(drop=True)

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

        cal = {}
        lim = df[df["is_limit"]]
        for d, g in lim.groupby("date"):
            cal[d] = g[["code", "boards", "close", "pct"]].reset_index(drop=True)
        price = {}
        for code, g in df.groupby("code"):
            price[code] = g[["date", "close", "pct"]].reset_index(drop=True)
        trade_dates = sorted(df["date"].unique())
        print(f"从缓存加载 {DAILY_CACHE}：{len(df)} 行，用时 {time.time()-t0:.0f}s")
        return cal, price, trade_dates

    # 首次（或 --force）：拉取全市场（支持断点续传，fetch_all_daily 内部增量落盘）
    t0 = time.time()
    df = DB.fetch_all_daily(start, end, cache=DAILY_CACHE)
    print(f"全市场日线已缓存 {DAILY_CACHE}（{len(df)} 行），用时 {time.time()-t0:.0f}s")
    # 重建
    return get_market(start, end, force=False)


# ── 简化打分 ────────────────────────────────────────────

def score_day(pool: pd.DataFrame, total_limit_up: int) -> pd.DataFrame:
    df = pool.copy()
    def board_score(b):
        return 10.0 if b >= 4 else {1: 6, 2: 8, 3: 9}.get(int(b), 6)
    df["连板身位"] = df["boards"].apply(board_score)

    if total_limit_up <= 30:
        mood = 3.0
    elif total_limit_up <= 50:
        mood = 5.0
    elif total_limit_up <= 70:
        mood = 7.0
    elif total_limit_up <= 90:
        mood = 8.0
    elif total_limit_up <= 120:
        mood = 9.0
    else:
        mood = 10.0
    df["市场情绪"] = mood

    def pos_score(pct):
        if pct >= 19.8:
            return 10.0 if pct >= 19.95 else 9.0
        if pct >= 9.8:
            return 10.0 if pct >= 10.0 else 8.0
        return 6.0
    df["个股身位"] = df["pct"].apply(pos_score)

    def quality_score(pct):
        lim = 19.8 if pct >= 19.8 else 9.8
        gap = abs(pct - (lim + 0.2))
        return max(4.0, 10.0 - gap * 10)
    df["封板质量"] = df["pct"].apply(quality_score)

    df["题材强度"] = 7.0
    score = (df["连板身位"] * 0.25 + df["市场情绪"] * 0.25 + df["个股身位"] * 0.25
             + df["封板质量"] * 0.15 + df["题材强度"] * 0.10)
    df["综合分"] = (10.0 * score).round(1)
    return df.sort_values("综合分", ascending=False).reset_index(drop=True)


# ── 回测 ────────────────────────────────────────────────

def run(start: str, end: str, top_n: int, force: bool = False,
        first_board_only: bool = False) -> pd.DataFrame:
    """回测。first_board_only=True 时只在当日首板池（boards==1）内打分选股，
    直接回答「哪些首板大概率连板」。"""
    cal, price, trade_dates = get_market(start, end, force=force)
    dates = sorted(cal.keys())
    # 只用 trade_dates 内的交易日（cal 键都是交易日，这里直接过滤掉最后的无次日日）
    usable = [d for d in dates if d in trade_dates]

    recs = []
    for i, d in enumerate(usable):
        idx = trade_dates.index(d)
        if idx + 1 >= len(trade_dates):
            continue
        next_d = trade_dates[idx + 1]
        pool = cal.get(d)
        if pool is None or pool.empty:
            continue
        if first_board_only:
            pool = pool[pool["boards"] == 1]
            if pool.empty:
                continue
        scored = score_day(pool, len(pool))
        picked = scored.head(top_n)
        for _, r in picked.iterrows():
            code = r["code"]
            buy_price = r["close"]
            # 次日价格：从全市场价格表查（涨停或非涨停都有）
            ptab = price.get(code)
            nxt = None
            if ptab is not None:
                row = ptab[ptab["date"] == next_d]
                if not row.empty:
                    nxt = row.iloc[0]
            if nxt is None:
                recs.append({"date": d, "code": code, "boards": r["boards"],
                             "score": r["综合分"], "buy_price": buy_price,
                             "next_pct": None, "is_limit_up": False, "ret": None})
                continue
            ret = (nxt["close"] - buy_price) / buy_price * 100.0
            # 次日是否涨停：次日出现在涨停日历即视为连板
            is_lim = False
            npool = cal.get(next_d)
            if npool is not None and not npool.empty:
                hit = npool[npool["code"] == code]
                if not hit.empty:
                    is_lim = True
            recs.append({"date": d, "code": code, "boards": r["boards"],
                         "score": r["综合分"], "buy_price": buy_price,
                         "next_pct": round(ret, 2), "is_limit_up": is_lim,
                         "ret": round(ret, 2)})
        if (i + 1) % 20 == 0 or i == len(usable) - 1:
            print(f"  进度 {i + 1}/{len(usable)} 日，累计 {len(recs)} 条")
    return pd.DataFrame(recs)


# ── 统计 ────────────────────────────────────────────────

def summarize(df: pd.DataFrame, label: str) -> dict:
    valid = df[df["ret"].notna()]
    n = len(valid)
    if n == 0:
        return {"label": label, "trades": 0}
    hit = int(valid["is_limit_up"].sum())
    win = int((valid["ret"] > 0).sum())
    avg = float(valid["ret"].mean())
    wins = valid[valid["ret"] > 0]["ret"]
    losses = valid[valid["ret"] <= 0]["ret"]
    pf = wins.sum() / abs(losses.sum()) if not losses.empty and losses.sum() != 0 else float("inf")
    return {
        "label": label, "trades": n,
        "hit_rate": round(hit / n * 100.0, 2),
        "avg_ret": round(avg, 2),
        "win_rate": round(win / n * 100.0, 2),
        "profit_factor": round(pf, 2) if pf != float("inf") else None,
    }


def baseline(cal, price, trade_dates, dates: list[str]) -> dict:
    """全池基准：每个交易日全部涨停股次日平均表现。"""
    recs = []
    for d in dates:
        idx = trade_dates.index(d)
        if idx + 1 >= len(trade_dates):
            continue
        next_d = trade_dates[idx + 1]
        pool = cal.get(d)
        if pool is None:
            continue
        for _, r in pool.iterrows():
            ptab = price.get(r["code"])
            if ptab is None:
                continue
            row = ptab[ptab["date"] == next_d]
            if row.empty:
                continue
            ret = (row.iloc[0]["close"] - r["close"]) / r["close"] * 100.0
            recs.append({"date": d, "code": r["code"], "ret": ret,
                         "is_limit_up": False})
    # 重算 is_limit_up：次日是否在涨停池
    for rec in recs:
        d, code = rec["date"], rec["code"]
        idx = trade_dates.index(d)
        if idx + 1 < len(trade_dates):
            npool = cal.get(trade_dates[idx + 1])
            if npool is not None and not npool.empty and (npool["code"] == code).any():
                rec["is_limit_up"] = True
    return summarize(pd.DataFrame(recs), "全池基准")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-06-02")
    ap.add_argument("--end", default="2026-09-18")
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--first-board", action="store_true",
                    help="只在首板池内选股（回答：哪些首板大概率连板）")
    args = ap.parse_args()

    print("=" * 66)
    mode = "首板专项" if args.first_board else "全池"
    print(f"baostock 长周期回测：{args.start} ~ {args.end}，Top{args.top_n}（{mode}）")
    print("=" * 66)

    recs = run(args.start, args.end, args.top_n, force=args.force,
               first_board_only=args.first_board)
    if recs.empty:
        print("!! 无有效回测记录")
        raise SystemExit(1)
    recs.to_csv("backtest_baostock.csv", index=False, encoding="utf-8-sig")
    print(f"已保存: backtest_baostock.csv（{len(recs)} 条）")

    print("\n── 模型选股 ──")
    print(summarize(recs, f"模型 Top{args.top_n}"))

    cal, price, trade_dates = get_market(args.start, args.end, force=False)
    dates = sorted(recs["date"].unique())
    print("\n── 对照 ──")
    print(baseline(cal, price, trade_dates, dates))

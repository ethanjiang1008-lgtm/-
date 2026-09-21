# -*- coding: utf-8 -*-
"""baostock 长周期回测 v2：全市场日线一次性拉取 → 本地构建涨停日历与价格表
→ 逐日打分选股 → 尾盘买入（涨停收盘价）→ 次日判定连板/收益。

v2 升级（2026-09）：
  - 新因子：近10日涨停次数 lim10、5日动量 mom5（回测数据证实区分度强）
  - 身位权重拉开差距（6板+ 10 / 5板 9 / 4板 8 / 3板 7 / 2板 6 / 1板 5）
  - 出手过滤 --min-boards：只做当日最高分且身位达标者（宁缺毋滥）
  - 每笔输出因子得分，可解释预测原因

回测区间可任意设置（如近 1 年 250 交易日），不受涨停池接口近端限制。
简化因子（baostock 无封板时间/炸板次数/封板资金）：
  连板身位30% + 涨停频率20% + 5日动量15% + 个股身位15% + 封板质量10% + 市场情绪10%
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
        # v2 新因子：5日动量 + 近10日涨停次数（不含当日）
        g = df.groupby("code", sort=False)
        df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
        df["lim10"] = g["is_limit"].transform(
            lambda s: s.rolling(10, min_periods=1).sum().shift(1))

        cal = {}
        lim = df[df["is_limit"]]
        for d, g in lim.groupby("date"):
            cal[d] = g[["code", "boards", "close", "pct", "mom5", "lim10"]].reset_index(drop=True)
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


# ── v2 简化打分（含新因子与原因解释）────────────────

def _board_score(b):
    """连板身位：6板+ 10，5板 9，4板 8，3板 7，2板 6，1板 5（差距拉开）。"""
    b = int(b)
    if b >= 6:
        return 10.0
    return float({5: 9, 4: 8, 3: 7, 2: 6, 1: 5}.get(b, 5))


def _lim_score(x):
    """近10日涨停次数（不含当日）：≥5 10 / 4 9 / 3 8 / 2 6.5 / ≤1 4。"""
    if x >= 5:
        return 10.0
    if x >= 4:
        return 9.0
    if x >= 3:
        return 8.0
    if x >= 2:
        return 6.5
    return 4.0


def _mom_score(x):
    """5日动量：≥50% 10 / ≥30 9 / ≥20 8 / ≥10 7 / ≥0 5.5 / <0 4。"""
    if x >= 50:
        return 10.0
    if x >= 30:
        return 9.0
    if x >= 20:
        return 8.0
    if x >= 10:
        return 7.0
    if x >= 0:
        return 5.5
    return 4.0


def _pos_score(pct):
    if pct >= 19.8:
        return 10.0 if pct >= 19.95 else 9.0
    if pct >= 9.8:
        return 10.0 if pct >= 10.0 else 8.0
    return 6.0


def _qual_score(pct):
    lim = 19.8 if pct >= 19.8 else 9.8
    return max(4.0, 10.0 - abs(pct - (lim + 0.2)) * 10)


def _mood_score(n):
    if n <= 30:
        return 3.0
    if n <= 50:
        return 5.0
    if n <= 70:
        return 7.0
    if n <= 90:
        return 8.0
    if n <= 120:
        return 9.0
    return 10.0


# 权重：身位30% + 涨停频率20% + 动量15% + 个股15% + 封板质量10% + 情绪10%
W_BOARD, W_LIM, W_MOM, W_POS, W_QUAL, W_MOOD = 0.30, 0.20, 0.15, 0.15, 0.10, 0.10


def score_day(pool: pd.DataFrame, total_limit_up: int) -> pd.DataFrame:
    """v2 评分，输出各因子得分与综合分。pool 需含 boards/pct/mom5/lim10 列。"""
    df = pool.copy()
    df["连板身位"] = df["boards"].apply(_board_score)
    df["涨停频率"] = df["lim10"].apply(_lim_score)
    df["5日动量"] = df["mom5"].apply(_mom_score)
    df["个股身位"] = df["pct"].apply(_pos_score)
    df["封板质量"] = df["pct"].apply(_qual_score)
    df["市场情绪"] = _mood_score(total_limit_up)
    score = (df["连板身位"] * W_BOARD + df["涨停频率"] * W_LIM + df["5日动量"] * W_MOM
             + df["个股身位"] * W_POS + df["封板质量"] * W_QUAL + df["市场情绪"] * W_MOOD)
    df["综合分"] = (10.0 * score).round(1)
    return df.sort_values("综合分", ascending=False).reset_index(drop=True)


def score_day_fb(pool: pd.DataFrame, total_limit_up: int) -> pd.DataFrame:
    """首板专项评分：lim10（近10日涨停次数）绝对主导——回测证实它是首板
    晋级二板的最强因子（lim10≥5 命中率31% vs 基准16%，lim10≥3 时 TOP1 26.7%）。
    综合分 = 涨停频率分×10 + 动量分×0.5（lim10 决定顺序，mom5 仅作同分微调）；
    其余因子仍计算并保留，供原因解释。"""
    df = pool.copy()
    df["连板身位"] = 5.0
    df["涨停频率"] = df["lim10"].apply(_lim_score)
    df["5日动量"] = df["mom5"].apply(_mom_score)
    df["个股身位"] = df["pct"].apply(_pos_score)
    df["封板质量"] = df["pct"].apply(_qual_score)
    df["市场情绪"] = _mood_score(total_limit_up)
    df["综合分"] = (df["涨停频率"] * 10.0 + df["5日动量"] * 0.5).round(2)
    return df.sort_values("综合分", ascending=False).reset_index(drop=True)


def explain_row(r) -> str:
    """生成单只股票的预测理由（因子贡献 + 自然语言）。"""
    parts = []
    b = int(r["boards"])
    if b >= 6:
        parts.append(f"{b}板高位龙头，身位优势极大")
    elif b == 5:
        parts.append("5板高度，题材龙头候选")
    elif b == 4:
        parts.append("4板高度，连板梯队前排")
    elif b == 3:
        parts.append("3板高度，连板中位")
    elif b == 2:
        parts.append("2板高度，首板晋级后延续")
    else:
        parts.append("首板，连板起点")
    lim10 = float(r.get("lim10", 0))
    if lim10 >= 5:
        parts.append(f"近10日涨停{int(lim10)}次，资金反复攻击的强势股")
    elif lim10 >= 3:
        parts.append(f"近10日涨停{int(lim10)}次，近期活跃")
    elif lim10 >= 2:
        parts.append(f"近10日涨停{int(lim10)}次，有一定活跃度")
    else:
        parts.append("近期首次活跃，缺乏涨停惯性")
    mom = float(r.get("mom5", 0))
    if mom >= 30:
        parts.append(f"5日涨幅{mom:.0f}%，主升节奏")
    elif mom >= 15:
        parts.append(f"5日涨幅{mom:.0f}%，趋势向上")
    elif mom >= 0:
        parts.append(f"5日涨幅{mom:.0f}%，温和上行")
    else:
        parts.append(f"5日涨幅{mom:.0f}%，短期滞涨")
    if float(r["pct"]) >= 19.8:
        parts.append("20cm大板涨停，弹性大")
    else:
        parts.append("主板10cm涨停")
    return "；".join(parts)


# ── 回测 ────────────────────────────────────────────────

def run(start: str, end: str, top_n: int, force: bool = False,
        first_board_only: bool = False, min_boards: int = 0) -> pd.DataFrame:
    """回测。first_board_only=True 时只在当日首板池（boards==1）内打分选股，
    直接回答「哪些首板大概率连板」。min_boards>0 时只记录当日最高分且身位
    达标者的交易（宁缺毋滥，用于提升命中率）。"""
    cal, price, trade_dates = get_market(start, end, force=force)
    dates = sorted(cal.keys())
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
            scored = score_day_fb(pool, len(pool))
        else:
            scored = score_day(pool, len(pool))
        picked = scored.head(top_n)
        if min_boards > 0:
            # 只做「当日最高分且身位达标」的第一名（宁缺毋滥）
            top1 = scored.iloc[0]
            if int(top1["boards"]) < min_boards:
                continue
            picked = scored.head(1)
        for _, r in picked.iterrows():
            code = r["code"]
            buy_price = r["close"]
            ptab = price.get(code)
            nxt = None
            if ptab is not None:
                row = ptab[ptab["date"] == next_d]
                if not row.empty:
                    nxt = row.iloc[0]
            if nxt is None:
                recs.append({"date": d, "code": code, "boards": r["boards"],
                             "score": r["综合分"], "buy_price": buy_price,
                             "next_pct": None, "is_limit_up": False, "ret": None,
                             "reason": explain_row(r)})
                continue
            ret = (nxt["close"] - buy_price) / buy_price * 100.0
            is_lim = False
            npool = cal.get(next_d)
            if npool is not None and not npool.empty:
                hit = npool[npool["code"] == code]
                if not hit.empty:
                    is_lim = True
            recs.append({"date": d, "code": code, "boards": r["boards"],
                         "score": r["综合分"], "buy_price": buy_price,
                         "next_pct": round(ret, 2), "is_limit_up": is_lim,
                         "ret": round(ret, 2), "reason": explain_row(r)})
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
    ap.add_argument("--min-boards", type=int, default=0,
                    help=">0 时只做「当日最高分且身位≥N」的第一名（宁缺毋滥，提升命中率）")
    ap.add_argument("--out", default="backtest_baostock.csv")
    args = ap.parse_args()

    print("=" * 66)
    mode = "首板专项" if args.first_board else "全池"
    extra = f"，min_boards={args.min_boards}" if args.min_boards > 0 else ""
    print(f"baostock 长周期回测：{args.start} ~ {args.end}，Top{args.top_n}（{mode}{extra}）")
    print("=" * 66)

    recs = run(args.start, args.end, args.top_n, force=args.force,
               first_board_only=args.first_board, min_boards=args.min_boards)
    if recs.empty:
        print("!! 无有效回测记录")
        raise SystemExit(1)
    recs.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"已保存: {args.out}（{len(recs)} 条）")

    print("\n── 模型选股 ──")
    print(summarize(recs, f"模型 Top{args.top_n}" + (f"+身位≥{args.min_boards}" if args.min_boards else "")))

    cal, price, trade_dates = get_market(args.start, args.end, force=False)
    dates = sorted(recs["date"].unique())
    print("\n── 对照 ──")
    print(baseline(cal, price, trade_dates, dates))

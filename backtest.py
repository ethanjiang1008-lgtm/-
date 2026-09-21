# -*- coding: utf-8 -*-
"""回测引擎：逐交易日「涨停池 → 模型打分 → 尾盘买入 → 次日判定连板/收益」。

策略定义（用户口径）：
  - 当日收盘后选股：对当日涨停池用 8 因子模型打分，取概率 Top N
  - 尾盘买入：以当日收盘价（涨停价附近）买入
  - 次日判定：次日收盘价 >= 前收 × 1.099 → 连板命中（涨停）；
              次日跌停或大跌 → 亏损，按次日收盘涨跌幅计收益

输出：
  - 连板命中率（核心准确性指标）
  - 平均次日收益 / 胜率 / 盈亏比
  - 与全池基准、随机选股对照
"""

import random
import time
import pandas as pd

import config as C
import data_fetcher as F
import model as M


# ── 次日结果判定 ────────────────────────────────────────

def next_day_outcome(code: str, buy_date: str, buy_close: float) -> dict:
    """取 code 在 buy_date 之后首个交易日的行情，判定是否连板。

    返回 {date, close, pct_chg, is_limit_up, is_limit_down}
    涨停判定：pct_chg >= 9.8（主板 10%；创业板/科创板 20cm 由 pct_chg 反映，
    按 9.8 阈值对 20cm 会偏保守——但 20cm 股 pct_chg>=19.8 也必被捕获，此处
    统一用 >= 9.8 作为「至少涨停」口径，并在报告中分口径说明）。
    """
    dates = F.trade_dates()
    idx = dates.index(buy_date) if buy_date in dates else None
    if idx is None or idx + 1 >= len(dates):
        return None
    nd = dates[idx + 1]
    try:
        bars = F.daily_bars(code, buy_date, nd)
    except Exception:
        return None
    if bars.empty:
        return None
    row = bars[bars["date"] == nd]
    if row.empty:
        return None
    close = float(row["close"].iloc[0])
    pct = float(row["pct_chg"].iloc[0]) if "pct_chg" in row.columns else None
    if pct is None:
        prev_close = buy_close
        pct = (close - prev_close) / prev_close * 100.0
    return {
        "date": nd,
        "close": close,
        "pct_chg": round(pct, 2),
        "is_limit_up": pct >= 9.8,
        "is_limit_down": pct <= -9.8,
    }


# ── 单日回测 ────────────────────────────────────────────

def backtest_one_day(date: str, top_n: int = C.DEFAULT_TOP_N,
                     first_board_only: bool = False) -> list[dict]:
    """对单个交易日跑一遍完整策略，返回每只入选股的次日结果记录。
    first_board_only=True 时只在首板（连板数==1）内打分选股。"""
    pool = F.limit_up_pool(date)
    if pool.empty:
        return []

    if first_board_only:
        pool = pool[pool["连板数"] == 1]
        if pool.empty:
            return []

    total_limit_up = len(pool)
    scored = M.score_pool(pool, total_limit_up=total_limit_up)
    if scored.empty:
        return []

    # 概率 Top N（高于最低分线）
    picked = scored[scored["综合分"] >= C.MIN_SCORE].head(top_n)
    if picked.empty:
        picked = scored.head(top_n)

    results = []
    for _, row in picked.iterrows():
        code, name = str(row["代码"]), str(row["名称"])
        # 尾盘买入价 = 当日收盘价（涨停池"最新价"即当日收盘价，无需再拉日线）
        buy_close = float(row.get("最新价", 0)) if "最新价" in row.index else None
        if not buy_close or buy_close <= 0:
            bars = F.daily_bars(code, date, date)
            if bars.empty:
                continue
            buy_close = float(bars["close"].iloc[-1])
        outcome = next_day_outcome(code, date, buy_close)
        rec = {
            "date": date, "code": code, "name": name,
            "boards": int(row["连板数"]),
            "score": row["综合分"], "prob": row["次日连板概率"],
            "rating": row["评级"], "buy_price": round(buy_close, 2),
        }
        if outcome:
            rec.update({
                "next_date": outcome["date"],
                "next_close": outcome["close"],
                "next_pct": outcome["pct_chg"],
                "is_limit_up": outcome["is_limit_up"],
                "is_limit_down": outcome["is_limit_down"],
                "ret": round(outcome["pct_chg"], 2),   # 次日涨跌幅 = 持仓收益
            })
        else:
            rec.update({"next_date": None, "next_close": None, "next_pct": None,
                        "is_limit_up": False, "is_limit_down": False, "ret": None})
        results.append(rec)
    return results


# ── 全区间回测 ──────────────────────────────────────────

def run_backtest(start: str = None, end: str = None, days: int = C.BACKTEST_DEFAULT_DAYS,
                 top_n: int = C.DEFAULT_TOP_N, seed: int = 42,
                 first_board_only: bool = False) -> pd.DataFrame:
    """主回测入口。返回全部入选交易记录。"""
    dates = F.recent_trade_dates(end, days) if start is None else None
    if dates is None:
        all_dates = F.trade_dates()
        dates = [d for d in all_dates if start <= d <= end]

    all_records = []
    for i, d in enumerate(dates):
        try:
            recs = backtest_one_day(d, top_n=top_n, first_board_only=first_board_only)
        except Exception as e:
            print(f"  [{d}] 失败: {e}")
            time.sleep(3)
            try:
                recs = backtest_one_day(d, top_n=top_n)
            except Exception as e2:
                print(f"  [{d}] 重试仍失败: {e2}")
                recs = []
        all_records.extend(recs)
        if (i + 1) % 20 == 0 or i == len(dates) - 1:
            print(f"  进度 {i + 1}/{len(dates)} 日，累计记录 {len(all_records)} 条")
        time.sleep(1.0)   # 东财限流：日与日之间间隔 1s（涨停池缓存已去重）

    return pd.DataFrame(all_records)


# ── 统计口径 ────────────────────────────────────────────

def summarize(df: pd.DataFrame, label: str) -> dict:
    """对一组交易记录统计核心指标。"""
    valid = df[df["ret"].notna()]
    n = len(valid)
    if n == 0:
        return {"label": label, "trades": 0, "hit_rate": None, "avg_ret": None,
                "win_rate": None, "profit_factor": None, "max_drawdown": None}
    hit = int(valid["is_limit_up"].sum())
    win = int((valid["ret"] > 0).sum())
    avg = float(valid["ret"].mean())
    wins = valid[valid["ret"] > 0]["ret"]
    losses = valid[valid["ret"] <= 0]["ret"]
    pf = (wins.sum() / abs(losses.sum())) if not losses.empty and losses.sum() != 0 else float("inf")
    # 组合模拟：每日等权买入 N 只，次日卖出，日收益序列
    if "date" in valid.columns:
        daily = valid.groupby("date")["ret"].mean().sort_index()
        eq = (1 + daily / 100.0).cumprod()
        mdd = float(((eq / eq.cummax()) - 1).min()) * 100.0 if not eq.empty else 0.0
    else:
        mdd = 0.0
    return {
        "label": label, "trades": n,
        "hit_rate": round(hit / n * 100.0, 2),
        "avg_ret": round(avg, 2),
        "win_rate": round(win / n * 100.0, 2),
        "profit_factor": round(pf, 2) if pf != float("inf") else None,
        "max_drawdown": round(mdd, 2),
    }


def baseline_summary(pools: list[pd.DataFrame], dates: list[str]) -> dict:
    """全池基准：不筛选，对当日全部涨停股统计次日连板率（含首板与连板）。"""
    recs = []
    for d in dates:
        pool = F.limit_up_pool(d)
        if pool.empty:
            continue
        for _, row in pool.iterrows():
            code = str(row["代码"])
            buy_close = float(row.get("最新价", 0)) if "最新价" in row.index else None
            if not buy_close:
                continue
            out = next_day_outcome(code, d, buy_close)
            if out:
                recs.append({"date": d, "ret": out["pct_chg"], "is_limit_up": out["is_limit_up"]})
    return summarize(pd.DataFrame(recs), "全池基准（未筛选）")


def random_summary(dates: list[str], top_n: int, seed: int = 42) -> dict:
    """随机对照：每个交易日随机选 top_n 只涨停股，口径同上。"""
    rng = random.Random(seed)
    recs = []
    for d in dates:
        pool = F.limit_up_pool(d)
        if pool.empty:
            continue
        picked = pool.sample(min(top_n, len(pool)), random_state=seed) if len(pool) > top_n else pool
        for _, row in picked.iterrows():
            code = str(row["代码"])
            buy_close = float(row.get("最新价", 0)) if "最新价" in row.index else None
            if not buy_close:
                continue
            out = next_day_outcome(code, d, buy_close)
            if out:
                recs.append({"date": d, "ret": out["pct_chg"], "is_limit_up": out["is_limit_up"]})
    return summarize(pd.DataFrame(recs), "随机选股对照")


# ── 主入口 ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="首板连板概率模型 · 历史回测")
    ap.add_argument("--start", help="回测起始日 YYYY-MM-DD")
    ap.add_argument("--end", help="回测截止日 YYYY-MM-DD（含）")
    ap.add_argument("--days", type=int, default=C.BACKTEST_DEFAULT_DAYS, help="回测最近 N 个交易日")
    ap.add_argument("--top-n", type=int, default=C.DEFAULT_TOP_N, help="每日选概率 Top N")
    ap.add_argument("--first-board", action="store_true", help="只在首板池内选股")
    ap.add_argument("--out", default="backtest_results.csv", help="输出 CSV 路径")
    ap.add_argument("--skip-baseline", action="store_true", help="跳过全池基准（省时）")
    args = ap.parse_args()

    print("=" * 70)
    mode = "首板专项" if args.first_board else "全池"
    print("首板连板概率模型 · 历史回测" + f"（{mode}）")
    print(f"参数: start={args.start} end={args.end} days={args.days} top_n={args.top_n}")
    print("=" * 70)

    recs = run_backtest(start=args.start, end=args.end, days=args.days, top_n=args.top_n,
                        first_board_only=args.first_board)
    if recs.empty:
        print("!! 无有效回测记录，请检查网络/数据源/日期范围")
        raise SystemExit(1)
    recs.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"已保存明细: {args.out}（{len(recs)} 条）")

    print("\n── 模型选股结果 ──")
    print(summarize(recs, f"模型 Top{args.top_n}"))

    if not args.skip_baseline:
        dates = sorted(recs["date"].unique())
        print("\n── 对照 ──")
        print(baseline_summary([], dates))

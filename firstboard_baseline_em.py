# -*- coding: utf-8 -*-
"""东财版首板全池基准：对 days 窗口内每日首板（连板数==1）全部股票统计次日晋级率。
与 backtest.py --first-board 的模型 Top5 对比。"""
import pandas as pd
import config as C
import data_fetcher as F
import backtest as B


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    dates = F.recent_trade_dates(args.end, args.days)
    recs = []
    for i, d in enumerate(dates):
        try:
            pool = F.limit_up_pool(d)
        except Exception as e:
            print(f"  [{d}] 失败: {e}")
            continue
        if pool.empty:
            continue
        fb = pool[pool["连板数"] == 1]
        for _, row in fb.iterrows():
            code = str(row["代码"])
            buy_close = float(row.get("最新价", 0)) if "最新价" in row.index else None
            if not buy_close:
                continue
            out = B.next_day_outcome(code, d, buy_close)
            if out:
                recs.append({"date": d, "ret": out["pct_chg"],
                             "is_limit_up": out["is_limit_up"]})
        if (i + 1) % 20 == 0:
            print(f"  进度 {i+1}/{len(dates)}")
    rdf = pd.DataFrame(recs)
    n = len(rdf)
    hit = int(rdf["is_limit_up"].sum())
    win = int((rdf["ret"] > 0).sum())
    print(f"\n东财首板全池基准（{rdf['date'].nunique()} 个交易日，{n} 笔）：")
    print(f"  次日连板命中率: {hit/n*100:.2f}%")
    print(f"  平均次日收益: {rdf['ret'].mean():.2f}%")
    print(f"  胜率: {win/n*100:.2f}%")


if __name__ == "__main__":
    main()

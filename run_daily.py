# -*- coding: utf-8 -*-
"""每日选股入口：获取最近交易日（或指定日）涨停池 → 模型打分 → 概率榜 + 自动生成预测网页。

用法：
  python run_daily.py                 # 最近一个交易日，生成 daily_prediction_YYYYMMDD.html
  python run_daily.py --date 2026-09-18
  python run_daily.py --top-n 10 --out daily_result.csv
"""

import argparse
import os
import sys

import pandas as pd

import config as C
import data_fetcher as F
import model as M
import make_daily_html as DH


def main():
    ap = argparse.ArgumentParser(description="首板连板概率模型 · 每日选股")
    ap.add_argument("--date", help="交易日 YYYY-MM-DD；缺省取最近交易日")
    ap.add_argument("--top-n", type=int, default=0, help="只打印概率 Top N（0=全部）")
    ap.add_argument("--out", help="可选：保存评分结果 CSV")
    ap.add_argument("--no-html", action="store_true", help="跳过生成预测网页")
    args = ap.parse_args()

    if args.date:
        date = args.date
    else:
        date = F.recent_trade_dates(n=1)[-1]   # 最近一个 ≤ 今天的交易日（日历含未来日期，必须截断）

    print(f"交易日: {date}")
    pool = F.limit_up_pool(date)
    if pool.empty:
        print("!! 该日无涨停池数据（可能非交易日或数据源未更新）")
        return

    print(f"涨停池: {len(pool)} 只")
    temp = F.market_temperature(date)
    print(f"市场温度: 涨停 {temp['limit_up']} / 连板 {temp['lianban']} / 最高板 {temp['max_board']}")

    scored = M.score_pool(pool, total_limit_up=len(pool))
    out = scored.copy()
    out["代码"] = out["代码"].astype(str).str.zfill(6)

    if args.top_n:
        out = out.head(args.top_n)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.unicode.east_asian_width", True)
    print("\n" + out.to_string(index=False))

    if args.out:
        out.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n已保存: {args.out}")

    if not args.no_html:
        try:
            path = DH.make_daily_html(scored, date, temp)
            print(f"\n预测网页已生成: {path}")
            print("用浏览器打开即可查看可视化预测结果。")
        except Exception as e:
            print(f"\n[警告] 网页生成失败（不影响 CSV/终端结果）: {e}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""每日选股入口（v2）：获取最近交易日（或指定日）涨停池 → 计算 v2 因子
（5日动量 / 近10日涨停次数，优先本地缓存，缺失时实时拉取）→ 模型打分 →
概率榜 + 每只股票预测理由 + 自动生成预测网页。

用法：
  python run_daily.py                 # 最近一个交易日，生成 daily_prediction_YYYYMMDD.html
  python run_daily.py --date 2026-09-18
  python run_daily.py --top-n 10 --out daily_result.csv
  python run_daily.py --first-board   # 首板专项模式（只预测首板晋级二板）
"""

import argparse
import os
import sys

import pandas as pd

import config as C
import data_fetcher as F
import model as M
import make_daily_html as DH

BS_CACHE = "bs_daily_all.csv"


def v2_factors(date: str) -> tuple[dict, dict]:
    """返回 ({代码: 5日动量%}, {代码: 近10日涨停次数不含当日})。

    优先从 baostock 本地缓存取（快）；缓存缺当日时实时计算：
      - 近10日涨停次数：拉最近 11 个交易日涨停池统计
      - 5日动量：新浪日线接口拉当日涨停股最近 6 个交易日
    """
    if os.path.exists(BS_CACHE):
        try:
            df = pd.read_csv(BS_CACHE, dtype={"code": str})
            df = df.sort_values(["code", "date"]).reset_index(drop=True)

            def thresh(row):
                if row["is_st"]:
                    return 9.8 if row["code"].startswith(("3", "68")) else 4.8
                return 19.8 if row["code"].startswith(("3", "68")) else 9.8
            df["thresh"] = df.apply(thresh, axis=1)
            df["is_limit"] = df["pct"] >= df["thresh"] - 1e-6
            g = df.groupby("code", sort=False)
            df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
            df["lim10"] = g["is_limit"].transform(
                lambda s: s.rolling(10, min_periods=1).sum().shift(1))
            day = df[df["date"] == date]
            if not day.empty:
                mom5_map = dict(zip(day["code"], day["mom5"]))
                lim10_map = dict(zip(day["code"], day["lim10"]))
                print(f"[v2因子] 本地缓存命中 {date}（{len(day)} 只）")
                return mom5_map, lim10_map
            print(f"[v2因子] 缓存无 {date}，改用实时计算…")
        except Exception as e:
            print(f"[v2因子] 缓存读取失败（{e}），改用实时计算…")
    else:
        print("[v2因子] 无本地缓存，实时计算…")

    tds = F.recent_trade_dates(end_date=date, n=12)
    today_pool = F.limit_up_pool(date)
    codes = [str(c).strip().zfill(6) for c in today_pool["代码"]]

    # 近10日涨停次数（不含当日）：统计 date 之前 10 个交易日
    prev = [d for d in tds if d < date][-10:]
    lim_count = {c: 0 for c in codes}
    for d in prev:
        p = F.limit_up_pool(d)
        if p.empty:
            continue
        for c in p["代码"]:
            c6 = str(c).strip().zfill(6)
            if c6 in lim_count:
                lim_count[c6] += 1
    lim10_map = {c: lim_count[c] for c in codes}

    # 5日动量：最近 6 个交易日（含当日）收盘价
    mom5_map = {}
    for i, c in enumerate(codes):
        bars = F.daily_bars(c, prev[-5], date)
        if bars is not None and len(bars) >= 2:
            close_prev = bars.iloc[0]["close"]
            close_now = bars.iloc[-1]["close"]
            mom5_map[c] = round((close_now / close_prev - 1) * 100, 2)
        else:
            mom5_map[c] = None
        if (i + 1) % 20 == 0:
            print(f"  [动量] {i + 1}/{len(codes)} 只")
    return mom5_map, lim10_map


def main():
    ap = argparse.ArgumentParser(description="首板连板概率模型 · 每日选股（v2）")
    ap.add_argument("--date", help="交易日 YYYY-MM-DD；缺省取最近交易日")
    ap.add_argument("--top-n", type=int, default=0, help="只打印概率 Top N（0=全部）")
    ap.add_argument("--out", help="可选：保存评分结果 CSV")
    ap.add_argument("--no-html", action="store_true", help="跳过生成预测网页")
    ap.add_argument("--first-board", action="store_true",
                    help="首板专项模式：只对首板打分排序（预测哪些首板晋级二板）")
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

    if args.first_board:
        if "连板数" in pool.columns:
            pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") == 1]
        print(f"首板池: {len(pool)} 只（首板专项模式）")
    else:
        print(f"涨停池: {len(pool)} 只")

    temp = F.market_temperature(date)
    print(f"市场温度: 涨停 {temp['limit_up']} / 连板 {temp['lianban']} / 最高板 {temp['max_board']}")

    mom5_map, lim10_map = v2_factors(date)
    scored = M.score_pool(pool, total_limit_up=len(pool),
                          mom5_map=mom5_map, lim10_map=lim10_map,
                          first_board_mode=args.first_board)
    out = scored.copy()
    out["代码"] = out["代码"].astype(str).str.zfill(6)

    if args.top_n:
        out = out.head(args.top_n)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.unicode.east_asian_width", True)
    show_cols = [c for c in ["代码", "名称", "所属行业", "连板数", "涨停次数", "动量值",
                             "综合分", "次日连板概率", "评级", "预测理由"] if c in out.columns]
    print("\n" + out[show_cols].to_string(index=False))

    if args.out:
        out.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n已保存: {args.out}")

    if not args.no_html:
        try:
            path = DH.make_daily_html(scored, date, temp)
            print(f"\n预测网页已生成: {path}")
            print("用浏览器打开即可查看可视化预测结果（含每只股票的预测理由）。")
        except Exception as e:
            print(f"\n[警告] 网页生成失败（不影响 CSV/终端结果）: {e}")


if __name__ == "__main__":
    main()

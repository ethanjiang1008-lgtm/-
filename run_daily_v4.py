# -*- coding: utf-8 -*-
"""v4 每日选股入口：东财涨停池 → 大成交额/低换手/放量过滤 → 身位分位校准 → 预测网页。

用法：
  python run_daily_v4.py                       # 最近交易日（收盘后），预测下一交易日
  python run_daily_v4.py --date 2026-09-22     # 指定交易日
  python run_daily_v4.py --top-n 10            # 只打印 Top N
"""
import argparse
import os
import sys
import time

import pandas as pd

import data_fetcher as F
import model_v4 as M4

BS_CACHE = "bs_daily_v3.csv.gz"


def v4_factors(date: str):
    """从缓存计算前5日均额映射 {code: amt5}（截至 date 前一日，含 date 当日缺失时用最近5日）。
    当日成交额直接用东财涨停池字段，不进缓存。"""
    if not os.path.exists(BS_CACHE):
        raise FileNotFoundError(f"缺少缓存 {BS_CACHE}")
    df = pd.read_csv(BS_CACHE, dtype={"code": str})
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    g = df.groupby("code", sort=False)
    df["amt5"] = g["amount"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    # 若缓存含当日（baostock 正常时），当日 amt5 应剔除当日自身
    if date in set(df["date"]):
        df["amt5"] = df.groupby("code")["amount"].transform(
            lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    last = df.groupby("code").tail(1)
    m = dict(zip(last["code"].apply(lambda c: str(c).strip().zfill(6)), last["amt5"]))
    # 过滤 NaN（新股/次新无5日均额）
    return {k: v for k, v in m.items() if v is not None and v > 0}


def main():
    ap = argparse.ArgumentParser(description="首板连板概率模型 · 每日选股（v4）")
    ap.add_argument("--date", help="交易日 YYYY-MM-DD；缺省取最近交易日")
    ap.add_argument("--top-n", type=int, default=0, help="只打印概率 Top N（0=全部）")
    ap.add_argument("--out", help="可选：保存评分结果 CSV")
    ap.add_argument("--no-html", action="store_true", help="跳过生成预测网页")
    args = ap.parse_args()

    date = args.date or F.recent_trade_dates(n=1)[-1]
    next_day = F.next_trade_date(date)
    print(f"交易日: {date} → 预测 {next_day} 连板")

    pool = F.limit_up_pool(date)
    if pool.empty:
        print(f"!! 该日无涨停池数据（{date} 为交易日，说明东财接口异常或当日数据未就绪）")
        sys.exit(1)

    temp = F.market_temperature(date)
    total_lim = temp["limit_up"]
    print(f"市场温度: 涨停 {total_lim} / 连板 {temp['lianban']} / 最高板 {temp['max_board']}")

    vol_map = v4_factors(date)
    print(f"[v4因子] 前5日均额缓存命中 {len(vol_map)} 只（截至最近缓存日）")

    low = M4.score_pool_v4(pool, amt5_map=vol_map, total_limit_up=total_lim, mode="low")
    fb = M4.score_pool_v4(pool, amt5_map=vol_map, total_limit_up=total_lim, mode="fb")
    print(f"低位池候选: {len(low)} 只（1-3板 且 放量<6）")
    print(f"首板专项候选: {len(fb)} 只（首板 且 换手<3%）")

    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.unicode.east_asian_width", True)
    show = ["代码", "名称", "所属行业", "连板数", "换手率", "放量倍数",
            "综合分", "次日连板概率", "评级", "预测理由"]
    if args.top_n:
        print("\n── 低位池 TOP%s ──" % args.top_n)
        print(low[show].head(args.top_n).to_string(index=False))
        print("\n── 首板专项 TOP%s ──" % args.top_n)
        print(fb[show].head(args.top_n).to_string(index=False))
    else:
        print("\n── 低位池榜 ──")
        print(low[show].to_string(index=False))

    if args.out:
        low.to_csv(args.out, index=False, encoding="utf-8-sig")

    if not args.no_html:
        try:
            import make_daily_html_v4 as DH4
            path = DH4.make_daily_html_v4(low, fb, date, next_day, total_lim)
            print(f"\n预测网页已生成: {path}")
        except Exception as e:
            print(f"\n[警告] 网页生成失败: {e}")


if __name__ == "__main__":
    main()

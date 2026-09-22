# -*- coding: utf-8 -*-
"""每日选股入口（v3 重建版）：东财涨停池 → v3 六因子（身位/涨停频率/动量/换手率/
放量/情绪）+ 消息面事件识别 → 分身位×分位校准概率 → 预测理由 → 预测网页。

用法：
  python run_daily_v3.py                       # 最近交易日（收盘后），预测下一交易日
  python run_daily_v3.py --date 2026-09-18     # 指定交易日
  python run_daily_v3.py --top-n 10            # 只打印 Top N
  python run_daily_v3.py --no-events           # 跳过新闻事件识别（更快）
"""
import argparse
import os
import sys
import time

import pandas as pd

import data_fetcher as F
import model_v3 as M3

BS_CACHE = "bs_daily_v3.csv.gz"


def v3_factors(date: str):
    """从 baostock v3 缓存计算 (mom5, lim10, turn, vol_ratio) 四张映射表。"""
    if not os.path.exists(BS_CACHE):
        raise FileNotFoundError(f"缺少 v3 缓存 {BS_CACHE}，请先运行 data_baostock_v3.py")
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
    df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))
    df["amt5"] = g["amount"].transform(lambda s: s.rolling(5, min_periods=1).mean().shift(1))
    df["vol_ratio"] = df["amount"] / df["amt5"].replace(0, pd.NA)

    day = df[df["date"] == date]
    if day.empty:
        raise ValueError(f"v3 缓存无 {date} 数据（可能数据未拉到此日）")
    def m(c):
        return str(c).strip().zfill(6)
    return (dict(zip(day["code"].apply(m), day["mom5"])),
            dict(zip(day["code"].apply(m), day["lim10"])),
            dict(zip(day["code"].apply(m), day["turn"])),
            dict(zip(day["code"].apply(m), day["vol_ratio"])))


def fetch_events(codes, max_workers: int = 8):
    """拉取个股当日新闻标题，返回 {code6: [标题...]}。失败静默跳过。"""
    import concurrent.futures as cf
    import akshare as ak

    def one(code):
        try:
            df = ak.stock_news_em(symbol=code)
            if df is None or df.empty:
                return code, []
            titles = df["新闻标题"].astype(str).tolist()[:20]
            return code, titles
        except Exception:
            return code, []

    out = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for code, titles in ex.map(one, codes):
            if titles:
                out[code] = titles
    return out


def main():
    ap = argparse.ArgumentParser(description="首板连板概率模型 · 每日选股（v3）")
    ap.add_argument("--date", help="交易日 YYYY-MM-DD；缺省取最近交易日")
    ap.add_argument("--top-n", type=int, default=0, help="只打印概率 Top N（0=全部）")
    ap.add_argument("--out", help="可选：保存评分结果 CSV")
    ap.add_argument("--no-html", action="store_true", help="跳过生成预测网页")
    ap.add_argument("--no-events", action="store_true", help="跳过新闻事件识别")
    ap.add_argument("--first-board", action="store_true", help="首板专项：只预测首板晋级二板")
    ap.add_argument("--max-boards", type=int, default=3, help=">0 时只做 1~N 板（默认 3，即优先 1-3 板，不做 4 板+）")
    args = ap.parse_args()

    date = args.date or F.recent_trade_dates(n=1)[-1]
    next_day = F.next_trade_date(date)
    print(f"交易日: {date} → 预测 {next_day} 连板")

    pool = F.limit_up_pool(date)
    if pool.empty:
        print(f"!! 该日无涨停池数据（{date} 为交易日，说明东财接口异常或当日数据未就绪）")
        sys.exit(1)

    if args.first_board:
        pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") == 1]
        print(f"首板池: {len(pool)} 只（首板专项）")
    elif args.max_boards:
        pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") <= args.max_boards]
        print(f"低位池: {len(pool)} 只（1-{args.max_boards}板）")
    else:
        print(f"涨停池: {len(pool)} 只")

    temp = F.market_temperature(date)
    total_lim = temp["limit_up"]
    print(f"市场温度: 涨停 {total_lim} / 连板 {temp['lianban']} / 最高板 {temp['max_board']}")

    mom5_map, lim10_map, turn_map, vol_map = v3_factors(date)
    print(f"[v3因子] 缓存命中 {date}（{len(mom5_map)} 只）")

    events_map = {}
    if not args.no_events:
        codes = [str(c).strip().zfill(6) for c in pool["代码"]]
        print(f"[事件] 拉取 {len(codes)} 只个股新闻…")
        t0 = time.time()
        events_map = fetch_events(codes)
        print(f"[事件] 完成（{len(events_map)} 只有新闻，用时 {time.time()-t0:.0f}s）")

    scored = M3.score_pool_v3(pool, mom5_map=mom5_map, lim10_map=lim10_map,
                              turn_map=turn_map, vol_ratio_map=vol_map,
                              total_limit_up=total_lim, events_map=events_map)
    scored["代码"] = scored["代码"].astype(str).str.zfill(6)
    scored["预测日期"] = date
    scored["预测标的日"] = next_day

    out = scored.copy()
    if args.top_n:
        out = out.head(args.top_n)

    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.unicode.east_asian_width", True)
    show_cols = [c for c in ["代码", "名称", "所属行业", "连板数", "换手率", "涨停次数",
                             "动量值", "综合分", "次日连板概率", "评级", "事件标签",
                             "预测理由"] if c in out.columns]
    print("\n" + out[show_cols].to_string(index=False))

    if args.out:
        scored.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n已保存: {args.out}")

    if not args.no_html:
        try:
            import make_daily_html_v3 as DH3
            path = DH3.make_daily_html_v3(scored, date, next_day, total_lim)
            print(f"\n预测网页已生成: {path}")
        except Exception as e:
            print(f"\n[警告] 网页生成失败: {e}")


if __name__ == "__main__":
    main()

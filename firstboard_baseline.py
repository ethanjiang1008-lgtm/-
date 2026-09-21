# -*- coding: utf-8 -*-
"""计算 baostock 1 年数据的首板全池基准：
对每个交易日的全部首板股（boards==1），统计次日涨停晋级率与平均收益。
"""
import pandas as pd
import data_baostock as DB

CACHE = "bs_daily_all.csv"


def main():
    df = pd.read_csv(CACHE, dtype={"code": str})
    df = df.sort_values(["code", "date"]).reset_index(drop=True)

    def thresh(row):
        if row["is_st"]:
            return 9.8 if row["code"].startswith(("3", "68")) else 4.8
        return 19.8 if row["code"].startswith(("3", "68")) else 9.8
    df["thresh"] = df.apply(thresh, axis=1)
    df["is_limit"] = df["pct"] >= df["thresh"] - 1e-6
    df["_grp"] = (~df["is_limit"]).groupby(df["code"]).cumsum()
    df["boards"] = df.groupby(["code", "_grp"])["is_limit"].cumsum().astype(int)
    df = df.drop(columns=["_grp"])

    trade_dates = sorted(df["date"].unique())
    # 首板池
    fb = df[(df["is_limit"]) & (df["boards"] == 1)].copy()
    price_map = {}
    for code, g in df.groupby("code"):
        price_map[code] = dict(zip(g["date"], g["close"]))

    recs = []
    for d in trade_dates:
        idx = trade_dates.index(d)
        if idx + 1 >= len(trade_dates):
            continue
        nd = trade_dates[idx + 1]
        sub = fb[fb["date"] == d]
        for _, r in sub.iterrows():
            code = r["code"]
            pm = price_map.get(code, {})
            if nd in pm:
                ret = (pm[nd] - r["close"]) / r["close"] * 100.0
                recs.append({"date": d, "ret": ret,
                             "is_limit_up": ret >= 9.3})

    rdf = pd.DataFrame(recs)
    n = len(rdf)
    hit = int(rdf["is_limit_up"].sum())
    win = int((rdf["ret"] > 0).sum())
    print(f"首板全池基准：{n} 笔（{rdf['date'].nunique()} 个交易日）")
    print(f"  次日连板命中率: {hit/n*100:.2f}%")
    print(f"  平均次日收益: {rdf['ret'].mean():.2f}%")
    print(f"  胜率: {win/n*100:.2f}%")

    # 月度
    rdf["month"] = rdf["date"].str[:7]
    print("\n月度首板晋级率：")
    for m, sub in rdf.groupby("month"):
        h = int(sub["is_limit_up"].sum())
        print(f"  {m}: {len(sub):>4} 笔 | 晋级率 {h/len(sub)*100:5.1f}% | 均收 {sub['ret'].mean():+.2f}%")


if __name__ == "__main__":
    main()

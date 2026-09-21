# -*- coding: utf-8 -*-
"""TOP1 命中率拆分：当日首板（次日晋级二板） vs 当日已连板（次日继续连板）。
另输出 Top1-5 整体拆分作参考。"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")


def load_ranked(path):
    df = pd.read_csv(path, dtype={"code": str})
    df = df.sort_values(["date", "code", "score"], ascending=[True, True, False])
    df = df.drop_duplicates(["date", "code"], keep="first").reset_index(drop=True)
    df["rank"] = df.groupby("date")["score"].rank(method="first", ascending=False).astype(int)
    return df[df["rank"] <= 5]


def stats(sub):
    n = len(sub)
    if n == 0:
        return None
    hit = int(sub["is_limit_up"].sum())
    win = int((sub["ret"] > 0).sum())
    return dict(n=n, hit_rate=hit / n * 100, avg_ret=sub["ret"].mean(),
                win_rate=win / n * 100)


def main():
    df = load_ranked("backtest_baostock_all.csv")

    print("=" * 66)
    print("全池模型 · TOP1（每日第1名）1 年回测拆分")
    print("=" * 66)
    for label, mask in [("首板（当日boards==1 → 次日晋级二板）", df["boards"] == 1),
                        ("已连板（当日boards>=2 → 次日继续连板）", df["boards"] >= 2)]:
        s = stats(df[(df["rank"] == 1) & mask])
        if s:
            print(f"{label}")
            print(f"  笔数 {s['n']:>5} ｜ 命中率 {s['hit_rate']:5.2f}% ｜ "
                  f"平均收益 {s['avg_ret']:+.2f}% ｜ 胜率 {s['win_rate']:.2f}%")

    print()
    print("=" * 66)
    print("TOP1 按当日连板身位细分（每日第1名）")
    print("=" * 66)
    t1 = df[df["rank"] == 1]
    for b, sub in t1.groupby("boards"):
        s = stats(sub)
        print(f"  {int(b)}板: n={s['n']:>4} 命中率 {s['hit_rate']:5.2f}% 均收 {s['avg_ret']:+.2f}% 胜率 {s['win_rate']:.2f}%")

    print()
    print("=" * 66)
    print("Top1-5 整体拆分（参考）")
    print("=" * 66)
    for label, mask in [("首板（boards==1）", df["boards"] == 1),
                        ("已连板（boards>=2）", df["boards"] >= 2)]:
        s = stats(df[mask])
        print(f"{label}: n={s['n']:>4} 命中率 {s['hit_rate']:5.2f}% 均收 {s['avg_ret']:+.2f}% 胜率 {s['win_rate']:.2f}%")

    # 基准：全涨停池（含首板+连板）分组的自然晋级率
    print()
    print("=" * 66)
    print("基准对照：全涨停池自然晋级率（未筛选，1年）")
    print("=" * 66)
    import data_baostock as DB
    import pandas as pd
    raw = pd.read_csv("bs_daily_all.csv", dtype={"code": str})
    raw = raw.sort_values(["code", "date"]).reset_index(drop=True)

    def thresh(row):
        if row["is_st"]:
            return 9.8 if row["code"].startswith(("3", "68")) else 4.8
        return 19.8 if row["code"].startswith(("3", "68")) else 9.8
    raw["thresh"] = raw.apply(thresh, axis=1)
    raw["is_limit"] = raw["pct"] >= raw["thresh"] - 1e-6
    raw["_grp"] = (~raw["is_limit"]).groupby(raw["code"]).cumsum()
    raw["boards"] = raw.groupby(["code", "_grp"])["is_limit"].cumsum().astype(int)
    raw = raw.drop(columns=["_grp"])
    tds = sorted(raw["date"].unique())
    px = {}
    for code, g in raw.groupby("code"):
        px[code] = dict(zip(g["date"], g["close"]))
    recs = []
    lim = raw[raw["is_limit"]]
    for d in tds:
        i = tds.index(d)
        if i + 1 >= len(tds):
            continue
        nd = tds[i + 1]
        for _, r in lim[lim["date"] == d].iterrows():
            pm = px.get(r["code"], {})
            if nd in pm:
                ret = (pm[nd] - r["close"]) / r["close"] * 100.0
                recs.append({"boards": int(r["boards"]), "ret": ret,
                             "hit": ret >= 9.3})
    bdf = pd.DataFrame(recs)
    for label, mask in [("首板（boards==1）", bdf["boards"] == 1),
                        ("已连板（boards>=2）", bdf["boards"] >= 2)]:
        sub = bdf[mask]
        n = len(sub)
        print(f"{label}: n={n:>5} 命中率 {int(sub['hit'].sum())/n*100:5.2f}% 均收 {sub['ret'].mean():+.2f}%")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""v3 多维因子探索：在 bs_daily_v3.csv（含 volume/amount/turn）上构建
量能因子（换手率/放量倍数），评估：
1) 新因子在 1 板/2 板/3 板各身位池内的区分度
2) 全因子权重网格搜索：找 TOP1/TOP3 命中率最高且训练/验证均衡的组合
3) 回应用户质疑：概率同质化 → 验证校准方案
"""
import itertools
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CACHE = "bs_daily_v3.csv.gz"
SPLIT = "2026-03-01"


def load(cache: str = CACHE):
    df = pd.read_csv(cache, dtype={"code": str})
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
    g = df.groupby("code", sort=False)
    df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
    df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))
    # 量能因子（v3 缓存才有）：5日均额、放量倍数、换手率（当日）
    if "amount" in df.columns:
        df["amt5"] = g["amount"].transform(lambda s: s.rolling(5, min_periods=1).mean().shift(1))
        df["vol_ratio"] = df["amount"] / df["amt5"].replace(0, pd.NA)
    else:
        df["turn"] = 8.0
        df["vol_ratio"] = 3.0
    return df


def link(df):
    tds = sorted(df["date"].unique())
    tdi = {d: i for i, d in enumerate(tds)}
    lim = df[df["is_limit"]].copy()
    lim["next_date"] = lim["date"].map(lambda d: tds[tdi[d] + 1] if tdi[d] + 1 < len(tds) else None)
    lim = lim[lim["next_date"].notna()]
    nxt = df[["code", "date", "close", "is_limit"]].rename(
        columns={"date": "next_date", "close": "next_close", "is_limit": "next_limit"})
    m = lim.merge(nxt, on=["code", "next_date"], how="left")
    m["hit"] = m["next_limit"].fillna(False)
    m["n_lim"] = m["date"].map(m.groupby("date").size())
    return m


def show(tag, df, ndays=None):
    n = len(df)
    if n == 0:
        print(f"  {tag}: n=0")
        return
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    line = (f"  {tag}: n={n:>4} 全期 {df['hit'].mean()*100:5.2f}% | "
            f"训练 {tr['hit'].mean()*100:5.2f}%({len(tr)}) / 验证 {va['hit'].mean()*100:5.2f}%({len(va)})")
    if ndays:
        line += f"  出手率 {df['date'].nunique()/ndays*100:.0f}%"
    print(line)


# 分档打分函数
def _turn_s(x):
    """换手率：<2% 惜售强 10 / <5% 8 / <10% 6 / <15% 4 / ≥15% 2；缺失中性 6"""
    if pd.isna(x):
        return 6.0
    if x < 2: return 10.0
    if x < 5: return 8.0
    if x < 10: return 6.0
    if x < 15: return 4.0
    return 2.0


def _vol_s(x):
    """放量倍数：<1.5 缩量 6 / <3 温和 8 / <6 放量 9 / <10 巨量 7 / ≥10 天量 4；缺失中性 7"""
    if pd.isna(x):
        return 7.0
    if x < 1.5: return 6.0
    if x < 3: return 8.0
    if x < 6: return 9.0
    if x < 10: return 7.0
    return 4.0


def _lim_s(x):
    if x >= 5: return 10.0
    if x >= 4: return 9.0
    if x >= 3: return 8.0
    if x >= 2: return 6.5
    return 4.0


def _mom_s(x):
    if x >= 50: return 10.0
    if x >= 30: return 9.0
    if x >= 20: return 8.0
    if x >= 10: return 7.0
    if x >= 0: return 5.5
    return 4.0


def _mood_s(n):
    if n <= 30: return 3.0
    if n <= 50: return 5.0
    if n <= 70: return 7.0
    if n <= 90: return 8.0
    if n <= 120: return 9.0
    return 10.0


def _board_s(b):
    b = int(b)
    if b >= 6: return 10.0
    return float({5: 9, 4: 8, 3: 7, 2: 6, 1: 5}.get(b, 5))


def build_features(m):
    df = m.copy()
    df["f_board"] = df["boards"].apply(_board_s)
    df["f_lim"] = df["lim10"].apply(_lim_s)
    df["f_mom"] = df["mom5"].apply(_mom_s)
    df["f_turn"] = df["turn"].apply(_turn_s)
    df["f_vol"] = df["vol_ratio"].apply(_vol_s)
    df["f_mood"] = df["n_lim"].apply(_mood_s)
    return df


def grid_search(m, weights_grid, top_n=1, low_only=False):
    """网格搜索：返回按全期 TOPn 命中率排序的权重组合。"""
    df = build_features(m)
    if low_only:
        df = df[df["boards"] <= 3]
    results = []
    for combo in weights_grid:
        w_board, w_lim, w_mom, w_turn, w_vol, w_mood = combo
        df["s"] = (df["f_board"] * w_board + df["f_lim"] * w_lim + df["f_mom"] * w_mom
                   + df["f_turn"] * w_turn + df["f_vol"] * w_vol + df["f_mood"] * w_mood)
        picked = df.sort_values("s", ascending=False).groupby("date").head(top_n)
        n = len(picked)
        if n < 50:
            continue
        all_h = picked["hit"].mean() * 100
        tr = picked[picked["date"] < SPLIT]
        va = picked[picked["date"] >= SPLIT]
        tr_h = tr["hit"].mean() * 100
        va_h = va["hit"].mean() * 100
        # 均衡得分：两段都高 + 差距小
        balance = min(tr_h, va_h) - abs(tr_h - va_h) * 0.5
        results.append((all_h, tr_h, va_h, balance, n, combo))
    results.sort(key=lambda r: -r[3])
    return results


def main():
    import sys as _sys
    cache = _sys.argv[1] if len(_sys.argv) > 1 else CACHE
    df = load(cache)
    m = link(df)
    ndays = m["date"].nunique()
    print(f"涨停样本 {len(m)}，交易日 {ndays}\n")

    print("═══ 1. 量能因子区分度（v3 新因子）═══")
    show("全池基准", m)
    show("turn<2%（缩量涨停）", m[m["turn"] < 2])
    show("turn<5%", m[m["turn"] < 5])
    show("turn 5-10%", m[(m["turn"] >= 5) & (m["turn"] < 10)])
    show("turn≥15%（高换手分歧）", m[m["turn"] >= 15])
    show("vol_ratio<1.5（缩量）", m[m["vol_ratio"] < 1.5])
    show("vol_ratio 1.5-3", m[(m["vol_ratio"] >= 1.5) & (m["vol_ratio"] < 3)])
    show("vol_ratio 3-6", m[(m["vol_ratio"] >= 3) & (m["vol_ratio"] < 6)])
    show("vol_ratio≥10（天量）", m[m["vol_ratio"] >= 10])
    show("turn<5 且 vol_ratio<3（缩量惜售）", m[(m["turn"] < 5) & (m["vol_ratio"] < 3)])
    show("turn<5 且 boards==1（首板缩量）", m[(m["turn"] < 5) & (m["boards"] == 1)])

    print("\n═══ 2. 分身位 × 量能（首板专项）═══")
    b1 = m[m["boards"] == 1]
    show("首板整体", b1)
    show("首板 turn<3", b1[b1["turn"] < 3])
    show("首板 turn<5", b1[b1["turn"] < 5])
    show("首板 turn 5-10", b1[(b1["turn"] >= 5) & (b1["turn"] < 10)])
    show("首板 vol_ratio<2", b1[b1["vol_ratio"] < 2])
    show("首板 vol_ratio 2-5", b1[(b1["vol_ratio"] >= 2) & (b1["vol_ratio"] < 5)])
    show("首板 vol_ratio≥5", b1[b1["vol_ratio"] >= 5])
    show("首板 turn<5 且 vol_ratio<3", b1[(b1["turn"] < 5) & (b1["vol_ratio"] < 3)])

    print("\n═══ 3. 全池权重网格搜索（TOP1）═══")
    grid = []
    for w_board in (0.25, 0.30, 0.35):
        for w_lim in (0.10, 0.15, 0.20):
            for w_mom in (0.05, 0.10, 0.15):
                for w_turn in (0.05, 0.10, 0.15):
                    for w_vol in (0.05, 0.10):
                        for w_mood in (0.05, 0.10):
                            s = w_board + w_lim + w_mom + w_turn + w_vol + w_mood
                            if abs(s - 1.0) < 1e-6:
                                grid.append((w_board, w_lim, w_mom, w_turn, w_vol, w_mood))
    print(f"  组合数 {len(grid)}")
    results = grid_search(m, grid, top_n=1)
    print("  Top10（按两段均衡得分）：")
    for all_h, tr_h, va_h, bal, n, combo in results[:10]:
        print(f"    {combo} → 全期 {all_h:.2f}% 训练 {tr_h:.2f}% 验证 {va_h:.2f}% (n={n})")

    print("\n═══ 4. 低位池（1-3板）权重网格搜索（TOP1）═══")
    results_low = grid_search(m, grid, top_n=1, low_only=True)
    print("  Top10（按两段均衡得分）：")
    for all_h, tr_h, va_h, bal, n, combo in results_low[:10]:
        print(f"    {combo} → 全期 {all_h:.2f}% 训练 {tr_h:.2f}% 验证 {va_h:.2f}% (n={n})")

    print("\n═══ 5. TOP3 全池网格 ═══")
    results3 = grid_search(m, grid, top_n=3)
    print("  Top10（按两段均衡得分）：")
    for all_h, tr_h, va_h, bal, n, combo in results3[:10]:
        print(f"    {combo} → 全期 {all_h:.2f}% 训练 {tr_h:.2f}% 验证 {va_h:.2f}% (n={n})")


if __name__ == "__main__":
    main()

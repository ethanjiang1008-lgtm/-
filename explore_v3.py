# -*- coding: utf-8 -*-
"""v3 探索：极致过滤规则 + 分段验证，目标「出手时 TOP1 命中率 ≥50%」。
聚焦高身位 + 涨停频率 + 动量组合，检查训练/验证两段是否都达标。"""
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

CACHE = "bs_daily_all.csv"


def load():
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
    g = df.groupby("code", sort=False)
    df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100
    df["lim5"] = g["is_limit"].transform(lambda s: s.rolling(5, min_periods=1).sum().shift(1))
    df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))
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
    m["ret"] = (m["next_close"] - m["close"]) / m["close"] * 100
    m["hit"] = m["next_limit"].fillna(False)
    m["n_lim"] = m["date"].map(m.groupby("date").size())
    return m


def show(title, sub, split="2026-03-01"):
    n = len(sub)
    if n == 0:
        print(f"  {title}: n=0")
        return
    hit = int(sub["hit"].sum())
    tr = sub[sub["date"] < split]
    va = sub[sub["date"] >= split]
    tr_h = int(tr["hit"].sum()) if len(tr) else 0
    va_h = int(va["hit"].sum()) if len(va) else 0
    print(f"  {title}: n={n:>4} 命中率 {hit/n*100:5.2f}% | "
          f"训练 {tr_h/max(1,len(tr))*100:4.1f}%({len(tr)}笔) / 验证 {va_h/max(1,len(va))*100:4.1f}%({len(va)}笔)")


def main():
    df = load()
    m = link(df)
    print(f"涨停样本 {len(m)}\n")

    print("═══ 规则 A：只看高身位（任意涨停日，非模拟打分）═══")
    for b, g in m.groupby("boards"):
        if int(b) >= 4:
            show(f"{int(b)}板", g)

    print("\n═══ 规则 B：高身位 × 涨停频率/动量 ═══")
    show("5板+ 且 lim10≥3", m[(m["boards"] >= 5) & (m["lim10"] >= 3)])
    show("6板+ 且 lim10≥3", m[(m["boards"] >= 6) & (m["lim10"] >= 3)])
    show("6板+ 且 lim10≥5", m[(m["boards"] >= 6) & (m["lim10"] >= 5)])
    show("5板+ 且 lim10≥5", m[(m["boards"] >= 5) & (m["lim10"] >= 5)])
    show("6板+ 且 mom5≥15", m[(m["boards"] >= 6) & (m["mom5"] >= 15)])
    show("7板+", m[m["boards"] >= 7])
    show("7板+ 且 lim10≥5", m[(m["boards"] >= 7) & (m["lim10"] >= 5)])
    show("6板+ 且 涨停<100", m[(m["boards"] >= 6) & (m["n_lim"] < 100)])
    show("5板+ 且 涨停<100 且 lim10≥3", m[(m["boards"] >= 5) & (m["n_lim"] < 100) & (m["lim10"] >= 3)])

    print("\n═══ 规则 C：模拟 TOP1 视角（每日最高分后过滤）═══")
    # 简化：直接按「boards×lim10」代理分排序取每日最高（近似模型偏好高身位高频率）
    m["rank_key"] = m["boards"] * 10 + m["lim10"].clip(0, 9) + (m["mom5"].clip(0, 50) / 50.0)
    top1 = m.sort_values("rank_key", ascending=False).groupby("date").head(1)
    show("TOP1 代理（boards+lim10+mom5）", top1)
    show("  ├ 且 boards≥5", top1[top1["boards"] >= 5])
    show("  ├ 且 boards≥6", top1[top1["boards"] >= 6])
    show("  └ 且 boards≥6 且 lim10≥3", top1[(top1["boards"] >= 6) & (top1["lim10"] >= 3)])

    print("\n═══ 规则 D：首板专项升级（首板池内按 lim10 排序）═══")
    fb = m[m["boards"] == 1]
    fb_top1 = fb.sort_values(["lim10", "mom5"], ascending=False).groupby("date").head(1)
    show("首板池 TOP1（按 lim10 排序）", fb_top1)
    show("  ├ 且 lim10≥3", fb_top1[fb_top1["lim10"] >= 3])
    show("  ├ 且 lim10≥4", fb_top1[fb_top1["lim10"] >= 4])
    show("  └ 且 lim10≥5", fb_top1[fb_top1["lim10"] >= 5])
    # 首板 TOP5 视角
    fb_top5 = fb.sort_values(["lim10", "mom5"], ascending=False).groupby("date").head(5)
    show("首板池 TOP5（按 lim10 排序）", fb_top5)
    show("  └ 且 lim10≥3", fb_top5[fb_top5["lim10"] >= 3])


if __name__ == "__main__":
    main()

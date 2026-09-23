# -*- coding: utf-8 -*-
"""构建最近一年沪深主板涨停样本集（非ST/非科创/非创业板）。
输出 zt_samples_mainboard.csv：T日涨停样本 + 次日连板标签 + 候选特征。

口径：
- 沪深主板 = 沪 60xxxx / 深 00xxxx（剔除 688 科创、300/301 创业、8/4/9 开头北交所）
- 涨停判定 = 收盘涨幅 >= 9.8%（主板非ST）
- 标签 y = T+1 日继续涨停（>=9.8%）
- 回测期 = 2025-09-22 ~ 2026-09-22（最近一年）
"""
import pandas as pd

START = "2025-09-22"
END = "2026-09-22"

df = pd.read_csv("bs_daily_v3.csv.gz", dtype={"code": str})
print(f"缓存: {len(df)} 行, {df['code'].nunique()} 只, 日期 {df['date'].min()}~{df['date'].max()}")

# 板块过滤：沪深主板
df = df[df["code"].str.match(r"^(60|00)\d{4}$")]
df = df[~df["is_st"]]
print(f"主板非ST: {len(df)} 行, {df['code'].nunique()} 只")

df = df.sort_values(["code", "date"]).reset_index(drop=True)
g = df.groupby("code", sort=False)

# 涨停判定（主板 10cm）
df["is_limit"] = df["pct"] >= 9.8 - 1e-6

# 连板数：连续涨停计数（T 日当天算连续第几板）
def _streak(s):
    out, cnt = [], 0
    for v in s:
        if v:
            cnt += 1
        else:
            cnt = 0
        out.append(cnt)
    return out
df["boards"] = g["is_limit"].transform(_streak)

# 特征（全部只用 T 日及之前信息，天然无前视）
df["mom5"] = df["close"] / g["close"].shift(5) * 100 - 100            # 5日涨幅(含T日)
df["mom20"] = df["close"] / g["close"].shift(20) * 100 - 100          # 20日涨幅
df["lim10"] = g["is_limit"].transform(lambda s: s.rolling(10, min_periods=1).sum().shift(1))  # 近10日涨停次数(不含T日)
df["lim20"] = g["is_limit"].transform(lambda s: s.rolling(20, min_periods=1).sum().shift(1))
df["amt5"] = g["amount"].transform(lambda s: s.rolling(5, min_periods=1).mean().shift(1))
df["vol_ratio"] = df["amount"] / df["amt5"].replace(0, pd.NA)          # 放量倍数(T日成交/前5日均额)
df["turn"] = pd.to_numeric(df["turn"], errors="coerce")
df["log_amt"] = (df["amount"] + 1).apply(lambda x: __import__("math").log10(x))
df["prev_pct"] = g["pct"].shift(1)                                     # 前一日涨幅
df["prev_limit"] = g["is_limit"].shift(1)                              # 前一日是否涨停

# 市场温度（当日全市场涨停家数，用主板池统计）
day_stats = df.groupby("date").agg(total_lim=("is_limit", "sum")).reset_index()
df = df.merge(day_stats, on="date", how="left")

# 次日是否涨停（标签）
df["next_limit"] = g["is_limit"].shift(-1)
df["next_pct"] = g["pct"].shift(-1)

# 取 T 日涨停样本（回测期内）
samp = df[(df["is_limit"]) & (df["date"] >= START) & (df["date"] <= END)].copy()
# 特征窗口完整：lim10/lim20 需要前10/20日数据（缓存起点2025-06-03，START前约80个交易日，足够）
samp = samp[samp["lim10"].notna() & samp["mom5"].notna() & samp["vol_ratio"].notna()]
samp["y"] = samp["next_limit"].fillna(False).astype(int)

print(f"样本: {len(samp)} 条（{samp['date'].nunique()} 个交易日）")
print(f"次日连板: {samp['y'].sum()}（{(samp['y'].mean()*100):.1f}%）")
print(f"身位分布:\n{samp['boards'].value_counts().sort_index()}")

cols = ["code", "date", "boards", "turn", "mom5", "mom20", "lim10", "lim20",
        "vol_ratio", "log_amt", "prev_pct", "prev_limit", "total_lim", "y"]
samp[cols].to_csv("zt_samples_mainboard.csv", index=False, encoding="utf-8-sig")
print("已保存 zt_samples_mainboard.csv")

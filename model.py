# -*- coding: utf-8 -*-
"""8 因子评分模型：输入涨停池 DataFrame，输出每只股票的因子分、综合分、概率、评级。"""

import pandas as pd
import config as C


# ────────────────────────── 因子打分 ──────────────────────────

def score_mood(total_limit_up: int) -> float:
    """市场情绪：全市场涨停家数分档。"""
    for upper, score in C.MOOD_LIMITS:
        if total_limit_up <= upper:
            return float(score)
    return 10.0


def score_seal_time(seal_time) -> float:
    """封板时间：'0930' 格式字符串，越早越高。"""
    if seal_time is None or (isinstance(seal_time, float) and pd.isna(seal_time)):
        return 5.0
    t = str(int(seal_time)).zfill(4) if isinstance(seal_time, (int, float)) else str(seal_time).strip()
    t = t.replace(":", "").replace("：", "")
    if not t or not t.isdigit():
        return 5.0
    t = t.zfill(4)
    for upper, score in C.SEAL_TIME_BUCKETS:
        if t <= upper:
            return float(score)
    return 2.0


def score_quality(bomb_times) -> float:
    """封板质量：炸板次数，0 次满分，每炸 1 次 -2，最低 2 分。"""
    if bomb_times is None or (isinstance(bomb_times, float) and pd.isna(bomb_times)):
        return 8.0
    n = int(bomb_times)
    return max(2.0, 10.0 - n * C.QUALITY_PER_BOMB)


def score_board_position(boards: int) -> float:
    """连板身位：1板=6，2板=8，3板=9，4板+=10。"""
    if boards >= 4:
        return 10.0
    return float(C.BOARD_POSITION_SCORE.get(boards, 6))


def score_ladder(top_board_in_theme: int) -> float:
    """板块梯队：题材内最高连板。"""
    if top_board_in_theme >= 4:
        return 10.0
    return float(C.LADDER_SCORE.get(top_board_in_theme, 5))


def score_position(mkt_cap_yi: float) -> float:
    """个股身位：流通市值越小分越高（小盘弹性）。"""
    if mkt_cap_yi is None or (isinstance(mkt_cap_yi, float) and pd.isna(mkt_cap_yi)):
        return 7.0
    for upper, score in C.POSITION_MKT_CAP_LIMITS:
        if mkt_cap_yi <= upper:
            return float(score)
    return 5.0


def score_theme_strength(theme_count: int) -> float:
    """题材强度：所属行业当日涨停家数。"""
    if theme_count >= 8:
        return 10.0
    if theme_count >= 5:
        return 9.0
    if theme_count >= 3:
        return 8.0
    if theme_count >= 2:
        return 7.0
    return 6.0


def score_fund(seal_amount_wan: float) -> float:
    """资金验证：封板资金（万元）。"""
    if seal_amount_wan is None or (isinstance(seal_amount_wan, float) and pd.isna(seal_amount_wan)):
        return 5.0
    for upper, score in C.FUND_LIMITS:
        if seal_amount_wan <= upper:
            return float(score)
    return 10.0


# ────────────────────────── 主评分入口 ──────────────────────────

def score_pool(df: pd.DataFrame, total_limit_up: int = None) -> pd.DataFrame:
    """对涨停池 DataFrame 逐行评分。

    必需列（AKShare stock_zt_pool_em 标准字段）：
      - 代码 / 名称
      - 连板数（首板=1）
      - 首次封板时间（'0930' 格式，或 '09:30:00'）
      - 炸板次数
      - 流通市值（元，AKShare 返回亿元？自动兼容处理）
      - 所属行业 / 行业
      - 封板资金（元）
      - 成交额（元）
    """
    df = df.copy()
    if total_limit_up is None:
        total_limit_up = len(df)

    # 归一化列名（兼容不同版本 AKShare 字段）
    ren = {}
    for src in ["代码", "股票代码", "代码/名称"]:
        if src in df.columns and "代码" not in ren:
            ren[src] = "代码"
    for src in ["名称", "股票简称"]:
        if src in df.columns and "名称" not in ren:
            ren[src] = "名称"
    for src in ["连板数", "涨停统计", "连续涨停天数"]:
        if src in df.columns and "连板数" not in ren:
            ren[src] = "连板数"
    for src in ["首次封板时间", "首次封板"]:
        if src in df.columns and "首次封板时间" not in ren:
            ren[src] = "首次封板时间"
    for src in ["炸板次数", "炸板"]:
        if src in df.columns and "炸板次数" not in ren:
            ren[src] = "炸板次数"
    for src in ["流通市值", "流通市值(元)"]:
        if src in df.columns and "流通市值" not in ren:
            ren[src] = "流通市值"
    for src in ["所属行业", "行业", "涨停原因类别"]:
        if src in df.columns and "所属行业" not in ren:
            ren[src] = "所属行业"
    for src in ["封板资金", "封板资金(元)"]:
        if src in df.columns and "封板资金" not in ren:
            ren[src] = "封板资金"
    df = df.rename(columns=ren)

    # 缺失列补默认值
    for col, default in [("连板数", 1), ("炸板次数", 0), ("所属行业", "其他"),
                         ("首次封板时间", None), ("流通市值", None), ("封板资金", None),
                         ("成交额", None)]:
        if col not in df.columns:
            df[col] = default

    # 连板数：AKShare 的"连板数"已含首板（1=首板）
    df["连板数"] = pd.to_numeric(df["连板数"], errors="coerce").fillna(1).astype(int)

    # 流通市值统一到"亿元"
    mkt = df["流通市值"]
    if mkt.dtype != object:
        if mkt.abs().max() > 1e8:   # 单位是元
            df["流通市值_亿"] = mkt / 1e8
        else:                        # 单位已是亿元
            df["流通市值_亿"] = mkt
    else:
        df["流通市值_亿"] = pd.to_numeric(mkt, errors="coerce") / 1e8

    # 封板资金统一到"万元"
    fund = df["封板资金"]
    if fund.dtype != object:
        if fund.abs().max() > 1e6:   # 单位是元
            df["封板资金_万"] = fund / 1e4
        else:                        # 单位已是万元
            df["封板资金_万"] = fund
    else:
        df["封板资金_万"] = pd.to_numeric(fund, errors="coerce") / 1e4

    # 题材强度：所属行业当日涨停家数
    theme_counts = df["所属行业"].value_counts()
    df["题材强度"] = df["所属行业"].map(theme_counts).apply(score_theme_strength)

    # 板块梯队：题材内最高连板
    theme_top_board = df.groupby("所属行业")["连板数"].max()
    df["板块梯队"] = df["所属行业"].map(theme_top_board).apply(score_ladder)

    # 市场情绪
    df["市场情绪"] = score_mood(total_limit_up)

    # 其余因子
    df["个股身位"] = df["流通市值_亿"].apply(score_position)
    df["封板时间"] = df["首次封板时间"].apply(score_seal_time)
    df["封板质量"] = df["炸板次数"].apply(score_quality)
    df["连板身位"] = df["连板数"].apply(score_board_position)
    df["资金验证"] = df["封板资金_万"].apply(score_fund)

    # 综合分
    def _composite(row):
        total = 0.0
        for factor, w in C.FACTOR_WEIGHTS.items():
            total += row[factor] * w
        return round(10.0 * total, 1)

    df["综合分"] = df.apply(_composite, axis=1)

    # 概率校准
    def _prob(row):
        boards = int(row["连板数"])
        base = C.BASE_PROMOTION_RATE.get(boards, C.BASE_PROMOTION_RATE[1])
        raw = base * (C.CALIBRATION_OFFSET + row["综合分"] / 100.0)
        return round(min(C.MAX_PROBABILITY, raw), 4)

    df["次日连板概率"] = df.apply(_prob, axis=1)

    # 评级
    def _rating(p):
        if p >= 0.40:
            return "A+ 强预期"
        if p >= 0.30:
            return "A"
        if p >= 0.20:
            return "B"
        if p >= 0.15:
            return "C"
        return "D"

    df["评级"] = df["次日连板概率"].apply(_rating)

    # 输出列（保留最新价/成交额，回测取尾盘买入价用）
    out_cols = ["代码", "名称", "所属行业", "连板数", "首次封板时间",
                "市场情绪", "题材强度", "板块梯队", "个股身位", "封板时间",
                "封板质量", "连板身位", "资金验证", "综合分", "次日连板概率", "评级",
                "最新价", "成交额"]
    keep = [c for c in out_cols if c in df.columns]
    return df[keep].sort_values("次日连板概率", ascending=False).reset_index(drop=True)

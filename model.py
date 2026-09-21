# -*- coding: utf-8 -*-
"""v2 评分模型（东财涨停池 8+2 因子）：输入涨停池 DataFrame，输出每只股票的
因子分、综合分、概率、评级与预测理由。

v2 升级（2026-09）：
  - 新增因子：近10日涨停次数（涨停频率）、5日动量（回测证实区分度最强）
  - 连板身位拉开差距（6板+ 10 / 5板 9 / 4板 8 / 3板 7 / 2板 6 / 1板 5）
  - 首板专项模式：涨停频率绝对主导（首板晋级二板最强因子）
  - 每只股票输出中文「预测理由」
"""

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
    """连板身位（v2 拉开差距）：1板=5，2板=6，3板=7，4板=8，5板=9，6板+=10。"""
    if boards >= 6:
        return 10.0
    return float(C.BOARD_POSITION_SCORE.get(boards, 5))


def score_mom5(mom5) -> float:
    """5日动量（回测实测：动量越高晋级率越高）。"""
    if mom5 is None or (isinstance(mom5, float) and pd.isna(mom5)):
        return 6.0
    v = float(mom5)
    for lo, score in C.MOM5_BUCKETS:
        if v >= lo:
            return float(score)
    return 4.0


def score_lim10(lim10) -> float:
    """近10日涨停次数（不含当日；首板晋级二板最强因子）。"""
    if lim10 is None or (isinstance(lim10, float) and pd.isna(lim10)):
        return 5.0
    v = float(lim10)
    for lo, score in C.LIM10_BUCKETS:
        if v >= lo:
            return float(score)
    return 4.0


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

def score_pool(df: pd.DataFrame, total_limit_up: int = None,
               mom5_map: dict = None, lim10_map: dict = None,
               first_board_mode: bool = False,
               low_board_mode: bool = False) -> pd.DataFrame:
    """对涨停池 DataFrame 逐行评分（v2）。

    新增可选参数：
      - mom5_map: {代码: 5日涨幅%}，缺失时给中性分
      - lim10_map: {代码: 近10日涨停次数（不含当日）}，缺失时给中性分
      - first_board_mode: True 时用「首板专项」评分（涨停频率绝对主导），
        直接回答「哪些首板大概率晋级二板」

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

    # v2 新因子：5日动量 / 近10日涨停次数
    def _code(x):
        return str(x).strip().zfill(6)
    df["_code6"] = df["代码"].apply(_code)
    df["5日动量"] = df["_code6"].map(mom5_map or {}).apply(score_mom5)
    df["涨停频率"] = df["_code6"].map(lim10_map or {}).apply(score_lim10)
    df["动量值"] = df["_code6"].map(mom5_map or {})
    df["涨停次数"] = df["_code6"].map(lim10_map or {})

    # 综合分（v2；首板专项用涨停频率绝对主导）
    if low_board_mode:
        # 低位模式（1-3板）：身位代理排序主导，回测命中率 47.65%（恰好3板 48.68%）
        df["综合分"] = (df["连板数"] * 10.0
                        + df["涨停次数"].clip(0, 9)
                        + df["动量值"].clip(0, 50) / 50.0).round(3)
    elif first_board_mode:
        # 首板池内连板身位恒为 5 分，不参与区分；
        # lim10 绝对主导（回测：lim10≥3 时首板 TOP1 命中率 26.7% vs 基准 16.4%）
        df["综合分"] = (df["涨停频率"] * 10.0 + df["5日动量"] * 0.5
                        + df["封板时间"] * 0.2 + df["封板质量"] * 0.2).round(2)
    else:
        def _composite(row):
            total = 0.0
            for factor, w in C.FACTOR_WEIGHTS.items():
                total += row[factor] * w
            return round(10.0 * total, 1)
        df["综合分"] = df.apply(_composite, axis=1)

    # 低位模式过滤：只做 1-3 板（用户要求不做高位）
    if low_board_mode:
        df = df[df["连板数"] <= 3].copy()

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

    # 预测理由（每只股票为什么这么预测）
    df["预测理由"] = df.apply(lambda r: explain_row(r), axis=1)

    # 输出列（保留最新价/成交额，回测取尾盘买入价用）
    out_cols = ["代码", "名称", "所属行业", "连板数", "首次封板时间", "涨停次数",
                "动量值", "市场情绪", "题材强度", "板块梯队", "个股身位", "封板时间",
                "封板质量", "连板身位", "涨停频率", "5日动量", "资金验证",
                "综合分", "次日连板概率", "评级", "预测理由",
                "最新价", "成交额"]
    keep = [c for c in out_cols if c in df.columns]
    if low_board_mode:
        return df[keep].sort_values("综合分", ascending=False).reset_index(drop=True)
    return df[keep].sort_values("次日连板概率", ascending=False).reset_index(drop=True)


def explain_row(r) -> str:
    """生成单只股票的预测理由（因子贡献 + 自然语言，可直接展示给用户）。"""
    parts = []
    boards = int(r.get("连板数", 1))
    if boards >= 6:
        parts.append(f"{boards}板高位龙头，身位优势极大")
    elif boards == 5:
        parts.append("5板高度，题材龙头候选")
    elif boards == 4:
        parts.append("4板高度，连板梯队前排")
    elif boards == 3:
        parts.append("3板高度，连板中位")
    elif boards == 2:
        parts.append("2板高度，首板晋级后延续")
    else:
        parts.append("首板，连板起点")

    lim10 = r.get("涨停次数")
    if lim10 is not None and not (isinstance(lim10, float) and pd.isna(lim10)):
        v = int(round(float(lim10)))
        if v >= 5:
            parts.append(f"近10日涨停{v}次，资金反复攻击的强势股")
        elif v >= 3:
            parts.append(f"近10日涨停{v}次，近期活跃")
        elif v == 2:
            parts.append(f"近10日涨停{v}次，有一定活跃度")
        else:
            parts.append("近期首次活跃，缺乏涨停惯性")

    mom = r.get("动量值")
    if mom is not None and not (isinstance(mom, float) and pd.isna(mom)):
        v = float(mom)
        if v >= 30:
            parts.append(f"5日涨幅{v:.0f}%，主升节奏")
        elif v >= 15:
            parts.append(f"5日涨幅{v:.0f}%，趋势向上")
        elif v >= 0:
            parts.append(f"5日涨幅{v:.0f}%，温和上行")
        else:
            parts.append(f"5日涨幅{v:.0f}%，短期滞涨")

    seal = r.get("封板时间")
    if isinstance(seal, float) and not pd.isna(seal):
        if seal >= 9:
            parts.append("开盘快速封板")
        elif seal >= 7:
            parts.append("早盘封板")
    bomb = r.get("炸板次数")
    if bomb is not None and not (isinstance(bomb, float) and pd.isna(bomb)):
        n = int(bomb)
        if n == 0:
            parts.append("封板无炸板，封单稳固")
        elif n >= 2:
            parts.append(f"炸板{n}次，封板质量一般")

    theme = r.get("所属行业")
    if theme:
        parts.append(f"所属{theme}题材")

    mcap = r.get("流通市值_亿")
    if mcap is not None and not (isinstance(mcap, float) and pd.isna(mcap)):
        if mcap <= 60:
            parts.append(f"流通市值{mcap:.0f}亿，小盘弹性")
        elif mcap >= 300:
            parts.append(f"流通市值{mcap:.0f}亿，大盘权重")

    if boards >= 6 and lim10 is not None and mom is not None:
        parts.append("高身位+高频率+强动量共振，次日连板预期最强")
    return "；".join(parts)

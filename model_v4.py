# -*- coding: utf-8 -*-
"""v4 评分模型（2026-09-23 迭代版）：
回测实证（主板非ST/科创/创业，242交易日，训练2025-09-22~2026-03-01 / 验证2026-03-02~09-21）：
  - 低位池(1-3板)：log_amt(成交额) 身位桶内分位校准 + 放量<6 过滤 → TOP1 65.7%（v3同口径52.5%）
  - 首板池专项：log_amt 校准 + 换手<3% 过滤 → TOP1 31.6%（v3同口径21.5%）
核心规律：同身位内换手越低晋级率越高（2板低换手58% vs 高换手27%；3板 79% vs 38%）；
          大成交额（log_amt高）且未天量分歧（放量<6）的 2-3 板票次日连板率最高。
"""
import json
import os

import numpy as np
import pandas as pd

CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib_v4.json")
NB = 5   # 分位档数


def _load_calib():
    if not os.path.exists(CALIB_PATH):
        return {}
    with open(CALIB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CALIB = _load_calib()


def _bucket(b):
    return str(int(b) if int(b) <= 3 else 4)


def prob_from_calib(calib_key, boards, q):
    """按 (身位桶, 因子分位) 查校准率。calib_key: "low"/"fb"。"""
    seg = CALIB.get(calib_key, {}).get(_bucket(boards))
    if not seg:
        return np.nan
    bin_i = min(int(q * NB), NB - 1)
    return float(seg[min(bin_i, len(seg) - 1)])


def score_pool_v4(pool, amt5_map=None, total_limit_up=None, events_map=None,
                  mode="low", sort_by="prob"):
    """v4 主评分。pool 为东财涨停池 DataFrame（含 代码/名称/连板数/换手率/成交额/所属行业）。

    mode="low": 低位池（1-3板），过滤 放量<6，按 log_amt 身位桶内分位校准
    mode="fb":  首板专项（1板），额外过滤 换手率<3%（惜售锁筹）
    amt5_map: {code: 前5日均额}（baostock 缓存滚动均值），用于计算当日放量倍数。
    返回带 次日连板概率/评级/预测理由/综合分(=log_amt分位分) 的 DataFrame，按概率降序。
    """
    df = pool.copy()
    for src, dst in [("代码", "代码"), ("股票代码", "代码"), ("名称", "名称"),
                     ("股票简称", "名称"), ("连板数", "连板数"), ("涨停统计", "连板数"),
                     ("连续涨停天数", "连板数"), ("换手率", "换手率"), ("换手", "换手率"),
                     ("成交额", "成交额"), ("所属行业", "所属行业"), ("行业", "所属行业"),
                     ("涨停原因类别", "所属行业")]:
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})
    for col, default in [("连板数", 1), ("所属行业", "其他"), ("换手率", None),
                         ("成交额", None), ("首次封板时间", None), ("封板资金", None),
                         ("炸板次数", 0), ("流通市值", None), ("最新价", None)]:
        if col not in df.columns:
            df[col] = default
    df["连板数"] = pd.to_numeric(df["连板数"], errors="coerce").fillna(1).astype(int)
    df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")

    def _c(x):
        return str(x).strip().zfill(6)
    df["_code6"] = df["代码"].apply(_c)

    # 成交额：优先东财当日值
    amt = pd.to_numeric(df["成交额"], errors="coerce")

    # 放量倍数 = 当日成交额 / 前5日均额（baostock 缓存 amt5_map）
    amt5 = df["_code6"].map(amt5_map or {})
    vr = amt / amt5.replace(0, np.nan)
    df["放量倍数"] = vr

    df["_logamt"] = np.log10(amt.where(amt.notna(), np.nan))
    df["次日连板概率"] = np.nan
    df["综合分"] = np.nan
    df["评级"] = "D"

    # ── 过滤（放量 NaN=当日成交额缺失，放行不误杀）──
    if mode == "fb":
        mask = (df["连板数"] == 1) & (df["换手率"] < 3.0)
    else:
        mask = (df["连板数"] <= 3) & (df["放量倍数"] < 6.0)
    mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
    if mode != "fb":
        mask = mask | (df["放量倍数"].isna())  # 成交额缺失放行
    sub_idx = df.index[mask]
    if len(sub_idx) == 0:
        df = df.iloc[0:0]
        return df

    sub = df.loc[sub_idx].copy()
    sub["_bucket"] = sub["连板数"].apply(_bucket)
    sub["_q"] = sub.groupby("_bucket")["_logamt"].rank(pct=True)
    sub["综合分"] = (sub["_q"] * 10).round(2)
    sub["次日连板概率"] = sub.apply(
        lambda r: prob_from_calib(mode, r["连板数"], r["_q"]) * 100.0, axis=1)

    def _rating(p):
        if p >= 60: return "A+ 强预期"
        if p >= 50: return "A"
        if p >= 35: return "B"
        if p >= 20: return "C"
        return "D"
    sub["评级"] = sub["次日连板概率"].apply(_rating)

    sub["预测理由"] = sub.apply(lambda r: explain_v4(r, mode), axis=1)

    keep = [c for c in ["代码", "名称", "所属行业", "连板数", "换手率", "放量倍数",
                        "综合分", "次日连板概率", "评级", "预测理由", "成交额",
                        "首次封板时间", "封板资金", "炸板次数", "最新价"] if c in sub.columns]
    sub = sub[keep]
    if sort_by == "prob":
        sub = sub.sort_values(["次日连板概率", "综合分"], ascending=False).reset_index(drop=True)
    else:
        sub = sub.sort_values("综合分", ascending=False).reset_index(drop=True)
    return sub


def explain_v4(r, mode) -> str:
    parts = []
    b = int(r.get("连板数", 1))
    if mode == "fb":
        parts.append("首板，连板起点")
    elif b == 2:
        parts.append("2板，首板晋级后延续")
    elif b == 3:
        parts.append("3板，连板中位")
    else:
        parts.append(f"{b}板")

    turn = r.get("换手率")
    if turn is not None and not pd.isna(turn):
        t = float(turn)
        if t < 2:
            parts.append(f"换手率{t:.1f}%极低，惜售锁筹（回测：同身位低换手晋级率58~79%）")
        elif t < 3 and mode == "fb":
            parts.append(f"换手率{t:.1f}%极低，惜售锁筹（回测：首板低换手晋级率31%）")
        elif t < 5:
            parts.append(f"换手率{t:.1f}%，筹码稳定")
        elif t >= 15:
            parts.append(f"换手率{t:.1f}%过高，分歧大晋级率低")

    amt = r.get("成交额")
    la = r.get("综合分")
    if amt is not None and not pd.isna(amt):
        try:
            yi = float(amt) / 1e8
            parts.append(f"成交额{yi:.1f}亿，资金关注度高（回测：大成交额晋级率高）")
        except (TypeError, ValueError):
            pass
    elif la is not None and not pd.isna(la):
        parts.append(f"成交额分位{la:.1f}")

    vr = r.get("放量倍数")
    if vr is not None and not pd.isna(vr):
        v = float(vr)
        if v < 1.5:
            parts.append("缩量涨停，筹码锁定")
        elif v < 3:
            parts.append(f"放量{v:.1f}倍，温和放量")
        elif v < 6:
            parts.append(f"放量{v:.1f}倍，未天量分歧")
        elif v >= 6:
            parts.append(f"放量{v:.1f}倍，天量分歧（已过滤）")

    theme = r.get("所属行业")
    if theme:
        parts.append(f"所属{theme}题材")

    prob = r.get("次日连板概率")
    if prob is not None and not pd.isna(prob):
        if prob >= 60:
            parts.append("同身位高分位，连板预期强")
        elif prob >= 35:
            parts.append("同身位中高分位")
        else:
            parts.append("同身位低分位，晋级概率有限")

    return "；".join(parts)

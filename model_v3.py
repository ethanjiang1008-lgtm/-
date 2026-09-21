# -*- coding: utf-8 -*-
"""v3 评分模型（2026-09 重建版）：
因子 = 连板身位30% + 涨停频率20% + 5日动量15% + 换手率15% + 放量倍数10% + 市场情绪10%
概率 = calib_v3.json 分身位×综合分分位校准（解决 v2 概率同质化）
增强 = 当日盘口（封板时间/封板资金/炸板）+ 消息面事件（重组/收购/中标等关键词）
"""
import json
import os

import pandas as pd

import config as C

V3_W = {"连板身位": 0.30, "涨停频率": 0.20, "5日动量": 0.15,
        "换手率": 0.15, "放量倍数": 0.10, "市场情绪": 0.10}

_EVENT_KEYWORDS = {
    "重组/收购": ["重组", "收购", "并购", "股权转让", "资产注入", "借壳", "实控人变更"],
    "业绩预增": ["预增", "业绩预告", "扭亏", "增长", "净利润"],
    "中标/订单": ["中标", "订单", "合同", "签约", "大单"],
    "增持/回购": ["增持", "回购", "举牌"],
    "AI/科技": ["人工智能", "AI", "算力", "大模型", "芯片", "机器人", "数据要素"],
    "政策/规划": ["政策", "规划", "获批", "核准", "批复", "入选"],
}

EVENT_WEIGHT = 0.8   # 事件命中对综合分的加成（0-10 分制）


def _load_calib():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib_v3.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


CALIB = _load_calib()


def _f_board(b):
    b = int(b)
    if b >= 6:
        return 10.0
    return float({5: 9, 4: 8, 3: 7, 2: 6, 1: 5}.get(b, 5))


def _f_lim(v):
    if pd.isna(v): return 4.0
    v = float(v)
    if v >= 5: return 10.0
    if v >= 4: return 9.0
    if v >= 3: return 8.0
    if v >= 2: return 6.5
    return 4.0


def _f_mom(v):
    if pd.isna(v): return 6.0
    v = float(v)
    if v >= 50: return 10.0
    if v >= 30: return 9.0
    if v >= 20: return 8.0
    if v >= 10: return 7.0
    if v >= 0: return 5.5
    return 4.0


def _f_turn(v):
    """换手率%：<2 惜售强 / <5 8 / <10 6 / <15 4 / ≥15 2"""
    if pd.isna(v): return 6.0
    v = float(v)
    if v < 2: return 10.0
    if v < 5: return 8.0
    if v < 10: return 6.0
    if v < 15: return 4.0
    return 2.0


def _f_vol(v):
    """放量倍数：<1.5 缩量 / <3 温和 / <6 放量 / <10 巨量 / ≥10 天量"""
    if pd.isna(v): return 7.0
    v = float(v)
    if v < 1.5: return 6.0
    if v < 3: return 8.0
    if v < 6: return 9.0
    if v < 10: return 7.0
    return 4.0


def _f_mood(n):
    if n <= 30: return 3.0
    if n <= 50: return 5.0
    if n <= 70: return 7.0
    if n <= 90: return 8.0
    if n <= 120: return 9.0
    return 10.0


def detect_events(news_list) -> tuple:
    """从新闻标题列表识别事件。返回 (事件标签, 事件说明)。
    负面语境（终止/取消/失败/亏损等）不构成加分事件。"""
    if not news_list:
        return None, ""
    neg = ["终止", "取消", "失败", "撤回", "亏损", "下滑", "减持", "问询", "立案", "处罚", "诉讼"]
    text = "；".join(str(x) for x in news_list)
    for label, kws in _EVENT_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text.lower():
                # 检查否定语境：关键词前后 12 个字内出现负面词则跳过
                idx = text.lower().find(kw.lower())
                ctx = text[max(0, idx - 12):idx + len(kw) + 12]
                if any(n in ctx for n in neg):
                    continue
                return label, text[:80]
    return None, ""


def score_pool_v3(pool: pd.DataFrame, mom5_map: dict = None, lim10_map: dict = None,
                  turn_map: dict = None, vol_ratio_map: dict = None,
                  total_limit_up: int = None, events_map: dict = None) -> pd.DataFrame:
    """v3 主评分。pool 为东财涨停池 DataFrame（含代码/名称/连板数/换手率/所属行业等）。"""
    df = pool.copy()
    if total_limit_up is None:
        total_limit_up = len(df)
    ren = {}
    for src in ["代码", "股票代码"]:
        if src in df.columns and "代码" not in ren:
            ren[src] = "代码"
    for src in ["名称", "股票简称"]:
        if src in df.columns and "名称" not in ren:
            ren[src] = "名称"
    for src in ["连板数", "涨停统计", "连续涨停天数"]:
        if src in df.columns and "连板数" not in ren:
            ren[src] = "连板数"
    for src in ["所属行业", "行业", "涨停原因类别"]:
        if src in df.columns and "所属行业" not in ren:
            ren[src] = "所属行业"
    for src in ["换手率", "换手"]:
        if src in df.columns and "换手率" not in ren:
            ren[src] = "换手率"
    df = df.rename(columns=ren)
    for col, default in [("连板数", 1), ("所属行业", "其他"), ("换手率", None),
                         ("首次封板时间", None), ("封板资金", None), ("炸板次数", 0)]:
        if col not in df.columns:
            df[col] = default
    df["连板数"] = pd.to_numeric(df["连板数"], errors="coerce").fillna(1).astype(int)

    def _c(x):
        return str(x).strip().zfill(6)
    df["_code6"] = df["代码"].apply(_c)

    # 六因子分
    df["f_board"] = df["连板数"].apply(_f_board)
    df["f_lim"] = df["_code6"].map(lim10_map or {}).apply(_f_lim)
    df["f_mom"] = df["_code6"].map(mom5_map or {}).apply(_f_mom)
    df["f_turn"] = df["_code6"].map(turn_map or {}).apply(_f_turn)
    df["f_vol"] = df["_code6"].map(vol_ratio_map or {}).apply(_f_vol)
    df["f_mood"] = _f_mood(total_limit_up)

    df["综合分"] = (df["f_board"] * V3_W["连板身位"] + df["f_lim"] * V3_W["涨停频率"]
                    + df["f_mom"] * V3_W["5日动量"] + df["f_turn"] * V3_W["换手率"]
                    + df["f_vol"] * V3_W["放量倍数"] + df["f_mood"] * V3_W["市场情绪"]).round(2)

    # 换手率列优先用东财当日值（更准），缺失时用 baostock 缓存
    if "换手率" in df.columns:
        turn_now = pd.to_numeric(df["换手率"], errors="coerce")
        df["换手率"] = turn_now.where(turn_now.notna(), df["_code6"].map(turn_map or {}))
    df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")

    # 封单强度（当日盘口增强）：封板资金/流通市值，一字板+高封单 = 强信号
    # 历史回测无法覆盖（baostock 无封单数据），概率上调部分标注「盘口增强，未回测」
    df["封单强度"] = 0.0
    df["封单强度分"] = 0.0
    if "封板资金" in df.columns and "流通市值" in df.columns:
        fund = pd.to_numeric(df["封板资金"], errors="coerce")
        mcap = pd.to_numeric(df["流通市值"], errors="coerce")
        df["封单强度"] = (fund / mcap.replace(0, pd.NA)).round(4)
        def _seal_s(x):
            if pd.isna(x): return 0.0
            if x >= 0.5: return 1.5    # 封单/流通市值 >50%：一字巨单
            if x >= 0.2: return 1.0
            if x >= 0.1: return 0.5
            return 0.0
        df["封单强度分"] = df["封单强度"].apply(_seal_s)
        df["综合分"] = df["综合分"] + df["封单强度分"]

    # 事件增强（消息面）
    df["事件标签"] = ""
    df["事件说明"] = ""
    if events_map:
        for i, row in df.iterrows():
            label, desc = detect_events(events_map.get(row["_code6"]))
            if label:
                df.at[i, "事件标签"] = label
                df.at[i, "事件说明"] = desc
                boost = EVENT_WEIGHT
                # 重组/收购 + 一字板（换手<1%）：首板最强事件驱动，额外加成
                if label == "重组/收购":
                    tr = df.at[i, "换手率"]
                    try:
                        if pd.notna(tr) and float(tr) < 1.0:
                            boost += 0.6
                    except (TypeError, ValueError):
                        pass
                df.at[i, "综合分"] = round(df.at[i, "综合分"] + boost, 2)

    # 概率校准（分身位×综合分分位）
    def _bucket(b):
        return int(b) if b <= 3 else 4

    def _prob(row):
        bk = str(_bucket(int(row["连板数"])))
        seg = CALIB.get(bk)
        if not seg:
            base = C.BASE_PROMOTION_RATE.get(int(row["连板数"]), 0.16)
        else:
            s = float(row["综合分"])
            best = seg[0]
            for q in seg:
                if s >= q["lo"]:
                    best = q
            base = float(best["rate"]) * (1.0 + min(0.25, max(0.0, s - best["hi"]) / 10.0))
        # 盘口增强（未回测）：封单强度每 0.5 档上调 8%，一字板+高封单最高 ×1.16
        boost = 1.0 + min(0.16, float(row.get("封单强度分", 0.0)) * 0.08)
        return round(min(C.MAX_PROBABILITY, base * boost), 4)

    df["次日连板概率"] = df.apply(_prob, axis=1)

    def _rating(p):
        if p >= 0.50: return "A+ 强预期"
        if p >= 0.40: return "A"
        if p >= 0.30: return "B"
        if p >= 0.20: return "C"
        return "D"

    df["评级"] = df["次日连板概率"].apply(_rating)

    df["预测理由"] = df.apply(lambda r: explain_v3(r), axis=1)

    out_cols = ["代码", "名称", "所属行业", "连板数", "换手率", "涨停次数", "动量值",
                "综合分", "次日连板概率", "评级", "事件标签", "封单强度", "预测理由",
                "最新价", "成交额", "首次封板时间", "封板资金", "炸板次数"]
    keep = [c for c in out_cols if c in df.columns]
    return df[keep].sort_values("综合分", ascending=False).reset_index(drop=True)


def explain_v3(r) -> str:
    """v3 预测理由：每只股票为什么这么预测（因子贡献 + 盘口 + 事件）。"""
    parts = []
    b = int(r.get("连板数", 1))
    if b == 1:
        parts.append("首板，连板起点")
    elif b == 2:
        parts.append("2板，首板晋级后延续")
    elif b == 3:
        parts.append("3板，连板中位")
    elif b == 4:
        parts.append("4板高度，梯队前排")
    else:
        parts.append(f"{b}板高位龙头")

    turn = r.get("换手率")
    if turn is not None and not (isinstance(turn, float) and pd.isna(turn)) and not pd.isna(turn):
        t = float(turn)
        if t < 2:
            parts.append(f"换手率{t:.1f}%极低，惜售锁筹（回测晋级率43%）")
        elif t < 5:
            parts.append(f"换手率{t:.1f}%，筹码稳定（回测晋级率28%）")
        elif t >= 15:
            parts.append(f"换手率{t:.1f}%过高，分歧大晋级率低")

    lim = r.get("涨停次数")
    if lim is not None and not (isinstance(lim, float) and pd.isna(lim)):
        v = int(round(float(lim)))
        if v >= 3:
            parts.append(f"近10日涨停{v}次，资金反复攻击")
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

    ev = r.get("事件标签")
    if ev:
        parts.append(f"消息面：{ev}")
        desc = r.get("事件说明")
        if desc:
            parts.append(f"（{desc[:40]}）")

    seal = r.get("封单强度")
    if seal is not None and not (isinstance(seal, float) and pd.isna(seal)) and not pd.isna(seal):
        s = float(seal)
        if s >= 0.5:
            parts.append(f"封单强度{s*100:.0f}%（封板资金/流通市值），一字巨单锁死")
        elif s >= 0.2:
            parts.append(f"封单强度{s*100:.0f}%，封单充裕")

    theme = r.get("所属行业")
    if theme:
        parts.append(f"所属{theme}题材")

    prob = r.get("次日连板概率")
    if prob is not None and not pd.isna(prob):
        if prob >= 0.5:
            parts.append("同身位高分位，连板预期强")
        elif prob >= 0.3:
            parts.append("同身位中高分位")
        else:
            parts.append("同身位低分位，晋级概率有限")

    return "；".join(parts)

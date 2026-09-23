# -*- coding: utf-8 -*-
"""算法迭代回测引擎 v1：多因子策略在主板涨停样本上的 TOPn 命中率对比。

口径（与用户锁定一致）：
- 样本：沪深主板非ST涨停股（2025-09-22 ~ 2026-09-21，242 交易日，14924 条）
- 策略：T 日收盘后按分数排序取 TOPn，次日继续涨停=命中
- 输出：位次命中率（每日 TOP1/TOP2/TOP3/TOP5 各自中标的交易日占比）
        + 池命中率（每日 TOP1-5 整体命中率）
- 分组：全池 / 低位池（1-3板）
"""
import numpy as np
import pandas as pd

S = pd.read_csv("zt_samples_mainboard.csv", dtype={"code": str})
S["date"] = pd.to_datetime(S["date"])
S = S.sort_values(["date", "code"]).reset_index(drop=True)

# 时间切分：训练 2025-09-22~2026-03-31，验证 2026-04-01~2026-09-21
TRAIN_END = pd.Timestamp("2026-03-31")
TR = S[S["date"] <= TRAIN_END].copy()
VA = S[S["date"] > TRAIN_END].copy()
print(f"训练 {TR['date'].nunique()} 日 / {len(TR)} 条；验证 {VA['date'].nunique()} 日 / {len(VA)} 条")


def daily_topn_hitrate(sub, score_col, topn_list=(1, 2, 3, 5), desc=True):
    """每日按 score_col 排序取 TOPn。
    返回 (位次命中率{1:..,2:..}, 池命中率{1:..,2:..,3:..,5:..})。
    位次命中率 = 每日排名第 n 的股票次日连板比例；
    池命中率 = 每日前 n 只合并后的命中比例。"""
    g = sub.copy()
    rng = np.random.RandomState(42)
    g["_rnd"] = rng.rand(len(g))
    g = g.sort_values(["date", score_col, "_rnd"], ascending=[True, desc, True])
    g["_rank"] = g.groupby("date").cumcount() + 1
    hit_pos, hit_pool = {}, {}
    for n in topn_list:
        pos = g[g["_rank"] == n]
        hit_pos[n] = pos["y"].mean() if len(pos) else np.nan
        pool = g[g["_rank"] <= n]
        hit_pool[n] = pool["y"].mean()
    return hit_pos, hit_pool


def show(tag, hit_pos, hit_pool):
    line = (f"{tag:<42s} TOP1 {hit_pos[1]*100:5.1f}%  TOP2 {hit_pos[2]*100:5.1f}%  "
            f"TOP3 {hit_pos[3]*100:5.1f}%  TOP5 {hit_pos[5]*100:5.1f}%  "
            f"池1-5 {hit_pool[5]*100:5.1f}%")
    print(line)
    return line


results = []
for name, sub in [("全池", S), ("低位池(1-3板)", S[S["boards"] <= 3])]:
    print(f"\n===== {name}（{sub['date'].nunique()} 日 / {len(sub)} 条）=====")
    # ---- 单因子排序 ----
    fmap = {
        "身位boards↓": ("boards", True),
        "换手turn↑(低换手优先)": ("turn", False),
        "5日动量mom5↓": ("mom5", True),
        "20日动量mom20↓": ("mom20", True),
        "近10日涨停lim10↓": ("lim10", True),
        "近20日涨停lim20↓": ("lim20", True),
        "放量vol_ratio↓": ("vol_ratio", True),
        "成交额log_amt↓": ("log_amt", True),
        "前日涨幅prev_pct↓": ("prev_pct", True),
    }
    for tag, (col, desc) in fmap.items():
        hp, pl = daily_topn_hitrate(sub, col, desc=desc)
        show(f"[单因子] {tag}", hp, pl)
    # ---- v3 六因子加权（离散映射，model_v3 口径）----
    def v3_score(r):
        import model_v3 as M3
        b = int(r["boards"])
        s = (M3._f_board(b) * 0.30 + M3._f_lim(r["lim10"]) * 0.20
             + M3._f_mom(r["mom5"]) * 0.15 + M3._f_turn(r["turn"]) * 0.15
             + M3._f_vol(r["vol_ratio"]) * 0.10 + M3._f_mood(r["total_lim"]) * 0.10)
        return round(s, 2)
    sub = sub.copy()
    sub["v3score"] = sub.apply(v3_score, axis=1)
    hp, pl = daily_topn_hitrate(sub, "v3score")
    show("[组合] v3六因子加权(现有)", hp, pl)
    # ---- 截面分位加权（可搜索基线）----
    sub["q_board"] = sub.groupby("date")["boards"].rank(pct=True)
    sub["q_turn"] = 1 - sub.groupby("date")["turn"].rank(pct=True)   # 低换手=高
    sub["q_mom5"] = sub.groupby("date")["mom5"].rank(pct=True)
    sub["q_lim10"] = sub.groupby("date")["lim10"].rank(pct=True)
    sub["q_vol"] = sub.groupby("date")["vol_ratio"].rank(pct=True)
    sub["q_mood"] = sub.groupby("date")["total_lim"].rank(pct=True)
    W = {"q_board": 0.30, "q_turn": 0.15, "q_mom5": 0.15, "q_lim10": 0.20,
         "q_vol": 0.10, "q_mood": 0.10}
    sub["qscore"] = sum(sub[k] * v for k, v in W.items())
    hp, pl = daily_topn_hitrate(sub, "qscore")
    show("[组合] 截面分位加权(等v3权重)", hp, pl)
    results.append((name, sub))

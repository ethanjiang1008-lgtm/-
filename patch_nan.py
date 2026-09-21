# -*- coding: utf-8 -*-
"""修复概率 nan bug：
1) model.py 低位模式综合分对缺失动量/涨停次数 fillna(0)，不产生 nan
2) model.py _prob 校准对 nan 安全：raw 非有限值时回退到基准概率"""
import io

P = "model.py"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

# 1) 低位模式综合分：缺失值兜底
old = """    if low_board_mode:
        # 低位模式（1-3板）：身位代理排序主导，回测命中率 47.65%（恰好3板 48.68%）
        df["综合分"] = (df["连板数"] * 10.0
                        + df["涨停次数"].clip(0, 9)
                        + df["动量值"].clip(0, 50) / 50.0).round(3)"""
new = """    if low_board_mode:
        # 低位模式（1-3板）：身位代理排序主导，回测命中率 47.65%（恰好3板 48.68%）
        # 注意：实时因子缺失（动量/涨停次数取数失败）时填 0，避免综合分 nan
        df["涨停次数"] = pd.to_numeric(df["涨停次数"], errors="coerce").fillna(0.0)
        df["动量值"] = pd.to_numeric(df["动量值"], errors="coerce").fillna(0.0)
        df["综合分"] = (df["连板数"] * 10.0
                        + df["涨停次数"].clip(0, 9)
                        + df["动量值"].clip(0, 50) / 50.0).round(3)"""
assert old in src, "low composite"
src = src.replace(old, new)

# 2) 概率校准：nan 安全（min(0.85, nan) 在 Python 中会返回 0.85，造成假高概率）
old = """    # 概率校准
    def _prob(row):
        boards = int(row["连板数"])
        base = C.BASE_PROMOTION_RATE.get(boards, C.BASE_PROMOTION_RATE[1])
        raw = base * (C.CALIBRATION_OFFSET + row["综合分"] / 100.0)
        return round(min(C.MAX_PROBABILITY, raw), 4)"""
new = """    # 概率校准（对缺失分数 nan 安全：raw 非有限时回退基准概率，避免 min() 误返回上限）
    def _prob(row):
        boards = int(row["连板数"])
        base = C.BASE_PROMOTION_RATE.get(boards, C.BASE_PROMOTION_RATE[1])
        score = row["综合分"]
        try:
            fscore = float(score)
            if not (fscore == fscore):   # nan 检测
                return round(base, 4)
            raw = base * (C.CALIBRATION_OFFSET + fscore / 100.0)
        except (TypeError, ValueError):
            return round(base, 4)
        return round(min(C.MAX_PROBABILITY, raw), 4)"""
assert old in src, "prob"
src = src.replace(old, new)

with io.open(P, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("model.py fixed")

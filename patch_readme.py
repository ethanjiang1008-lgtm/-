# -*- coding: utf-8 -*-
"""README 追加低位模式章节。"""
import io

P = "README.md"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

old = """- **精准模式**：只做「当日最高分且连板身位≥6」的第一名（宁缺毋滥），全期命中率 50.0%"""
new = """- **精准模式**：只做「当日最高分且连板身位≥6」的第一名（宁缺毋滥），全期命中率 50.0%
- **低位模式**：`--max-boards 3` 只做 1-3 板（不做高位，回测命中率 47.65%）；`--board-eq 3` 低位精准（只做当日最高分恰好 3 板的日子，命中率 48.68%，训练 50.0% / 验证 47.0%）。1-3 板池物理上限：3板自然晋级率 43.1% 是天花板，因子提升约 +6pp"""
assert old in src, "readme feature"
src = src.replace(old, new)

old = """# 首板专项
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 5 --first-board
# 精准模式：只做当日最高分且身位≥6 的第一名（命中率 50%）
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 1 --min-boards 6"""
new = """# 首板专项
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 5 --first-board
# 精准模式：只做当日最高分且身位≥6 的第一名（命中率 50%）
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 1 --min-boards 6
# 低位模式：只做 1-3 板（命中率 47.65%，每日出手）
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 1 --max-boards 3
# 低位精准：只做当日最高分恰好 3 板的日子（命中率 48.68%）
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 1 --max-boards 3 --board-eq 3"""
assert old in src, "readme cmd"
src = src.replace(old, new)

old = """# 首板专项（只预测首板晋级二板）
python run_daily.py --first-board"""
new = """# 首板专项（只预测首板晋级二板）
python run_daily.py --first-board
# 低位模式（只做 1-3 板，不做高位）
python run_daily.py --max-boards 3"""
assert old in src, "readme run"
src = src.replace(old, new)

with io.open(P, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("README patched")

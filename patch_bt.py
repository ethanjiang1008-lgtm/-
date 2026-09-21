# -*- coding: utf-8 -*-
"""对 backtest_baostock.py 做小补丁：加 --board-eq 低位精准参数。"""
import io

P = "backtest_baostock.py"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

# 1) run() 签名 + docstring
old_sig = """def run(start: str, end: str, top_n: int, force: bool = False,
        first_board_only: bool = False, min_boards: int = 0,
        max_boards: int = 0, mood_cap: int = 0) -> pd.DataFrame:
    \"\"\"回测。
    - first_board_only=True：只在首板池（boards==1）内打分选股
    - min_boards>0：只做「当日最高分且身位达标」的第一名（宁缺毋滥）
    - max_boards>0：低位模式，只在 1~max_boards 板内选股（身位代理排序）
    - mood_cap>0：当日全市场涨停家数超过上限则空仓
    \"\"\""""
new_sig = """def run(start: str, end: str, top_n: int, force: bool = False,
        first_board_only: bool = False, min_boards: int = 0,
        max_boards: int = 0, mood_cap: int = 0, board_eq: int = 0) -> pd.DataFrame:
    \"\"\"回测。
    - first_board_only=True：只在首板池（boards==1）内打分选股
    - min_boards>0：只做「当日最高分且身位达标」的第一名（宁缺毋滥）
    - max_boards>0：低位模式，只在 1~max_boards 板内选股（身位代理排序）
    - mood_cap>0：当日全市场涨停家数超过上限则空仓
    - board_eq>0：低位精准，只做「当日最高分恰好 N 板」的日子
    \"\"\""""
assert old_sig in src, "sig not found"
src = src.replace(old_sig, new_sig)

# 2) board_eq 过滤逻辑（插在 min_boards 过滤之后）
old_pick = """            picked = scored.head(1)
        for _, r in picked.iterrows():"""
new_pick = """            picked = scored.head(1)
        if board_eq > 0:
            # 低位精准：只做「当日最高分恰好 N 板」的日子（排除 1-2 板日的低晋级率股）
            top1 = scored.iloc[0]
            if int(top1["boards"]) != board_eq:
                continue
            picked = scored.head(1)
        for _, r in picked.iterrows():"""
assert old_pick in src, "pick not found"
src = src.replace(old_pick, new_pick)

# 3) argparse 参数
old_arg = """    ap.add_argument("--mood-cap", type=int, default=0,"""
new_arg = """    ap.add_argument("--board-eq", type=int, default=0,
                    help=">0 时低位精准：只做「当日最高分恰好 N 板」的日子")
    ap.add_argument("--mood-cap", type=int, default=0,"""
assert old_arg in src, "arg not found"
src = src.replace(old_arg, new_arg)

# 4) 传给 run()
old_call = """               max_boards=args.max_boards, mood_cap=args.mood_cap)"""
new_call = """               max_boards=args.max_boards, mood_cap=args.mood_cap,
               board_eq=args.board_eq)"""
assert old_call in src, "call not found"
src = src.replace(old_call, new_call)

# 5) 打印标签
old_lab = """                    + (f"+涨停≤{args.mood_cap}" if args.mood_cap else "")))"""
new_lab = """                    + (f"+恰好{args.board_eq}板" if args.board_eq else "")
                    + (f"+涨停≤{args.mood_cap}" if args.mood_cap else "")))"""
assert old_lab in src, "label not found"
src = src.replace(old_lab, new_lab)

# 6) extras
old_ex = """    extras = []
    if args.min_boards:"""
new_ex = """    extras = []
    if args.board_eq:
        extras.append(f"恰好{args.board_eq}板")
    if args.min_boards:"""
assert old_ex in src, "extras not found"
src = src.replace(old_ex, new_ex)

with io.open(P, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("patched OK")

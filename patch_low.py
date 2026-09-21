# -*- coding: utf-8 -*-
"""给 model.py 加 low_board_mode 参数，run_daily.py 加 --max-boards。"""
import io


def patch_model():
    P = "model.py"
    with io.open(P, encoding="utf-8") as f:
        src = f.read()

    # 1) score_pool 签名加 low_board_mode
    old = """def score_pool(df: pd.DataFrame, total_limit_up: int = None,
               mom5_map: dict = None, lim10_map: dict = None,
               first_board_mode: bool = False) -> pd.DataFrame:"""
    new = """def score_pool(df: pd.DataFrame, total_limit_up: int = None,
               mom5_map: dict = None, lim10_map: dict = None,
               first_board_mode: bool = False,
               low_board_mode: bool = False) -> pd.DataFrame:"""
    assert old in src, "model sig"
    src = src.replace(old, new)

    # 2) 综合分：低位模式分支
    old = """    if first_board_mode:
        # 首板池内连板身位恒为 5 分，不参与区分；
        # lim10 绝对主导（回测：lim10≥3 时首板 TOP1 命中率 26.7% vs 基准 16.4%）
        df["综合分"] = (df["涨停频率"] * 10.0 + df["5日动量"] * 0.5
                        + df["封板时间"] * 0.2 + df["封板质量"] * 0.2).round(2)
    else:"""
    new = """    if low_board_mode:
        # 低位模式（1-3板）：身位代理排序主导，回测命中率 47.65%（恰好3板 48.68%）
        df["综合分"] = (df["连板数"] * 10.0
                        + df["涨停次数"].clip(0, 9)
                        + df["动量值"].clip(0, 50) / 50.0).round(3)
    elif first_board_mode:
        # 首板池内连板身位恒为 5 分，不参与区分；
        # lim10 绝对主导（回测：lim10≥3 时首板 TOP1 命中率 26.7% vs 基准 16.4%）
        df["综合分"] = (df["涨停频率"] * 10.0 + df["5日动量"] * 0.5
                        + df["封板时间"] * 0.2 + df["封板质量"] * 0.2).round(2)
    else:"""
    assert old in src, "model composite"
    src = src.replace(old, new)

    # 3) 低位过滤 + 排序方式
    old = """    # 概率校准
    def _prob(row):"""
    new = """    # 低位模式过滤：只做 1-3 板（用户要求不做高位）
    if low_board_mode:
        df = df[df["连板数"] <= 3].copy()

    # 概率校准
    def _prob(row):"""
    assert old in src, "model filter"
    src = src.replace(old, new)

    # 4) 排序：低位模式按综合分（身位代理），其余按概率
    old = """    return df[keep].sort_values("次日连板概率", ascending=False).reset_index(drop=True)"""
    new = """    if low_board_mode:
        return df[keep].sort_values("综合分", ascending=False).reset_index(drop=True)
    return df[keep].sort_values("次日连板概率", ascending=False).reset_index(drop=True)"""
    assert old in src, "model sort"
    src = src.replace(old, new)

    with io.open(P, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("model.py patched")


def patch_run():
    P = "run_daily.py"
    with io.open(P, encoding="utf-8") as f:
        src = f.read()

    # 1) argparse
    old = """    ap.add_argument("--first-board", action="store_true",
                    help="首板专项模式：只对首板打分排序（预测哪些首板晋级二板）")
    args = ap.parse_args()"""
    new = """    ap.add_argument("--first-board", action="store_true",
                    help="首板专项模式：只对首板打分排序（预测哪些首板晋级二板）")
    ap.add_argument("--max-boards", type=int, default=0,
                    help=">0 时低位模式：只做 1~N 板（如 3 = 只做 1-3 板，不做高位）")
    args = ap.parse_args()"""
    assert old in src, "run args"
    src = src.replace(old, new)

    # 2) 池过滤提示
    old = """    if args.first_board:
        if "连板数" in pool.columns:
            pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") == 1]
        print(f"首板池: {len(pool)} 只（首板专项模式）")
    else:
        print(f"涨停池: {len(pool)} 只")"""
    new = """    if args.first_board:
        if "连板数" in pool.columns:
            pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") == 1]
        print(f"首板池: {len(pool)} 只（首板专项模式）")
    elif args.max_boards:
        if "连板数" in pool.columns:
            pool = pool[pd.to_numeric(pool["连板数"], errors="coerce") <= args.max_boards]
        print(f"低位池: {len(pool)} 只（1-{args.max_boards}板，不做高位）")
    else:
        print(f"涨停池: {len(pool)} 只")"""
    assert old in src, "run pool"
    src = src.replace(old, new)

    # 3) 传给 score_pool
    old = """    scored = M.score_pool(pool, total_limit_up=len(pool),
                          mom5_map=mom5_map, lim10_map=lim10_map,
                          first_board_mode=args.first_board)"""
    new = """    scored = M.score_pool(pool, total_limit_up=len(pool),
                          mom5_map=mom5_map, lim10_map=lim10_map,
                          first_board_mode=args.first_board,
                          low_board_mode=args.max_boards > 0)"""
    assert old in src, "run score"
    src = src.replace(old, new)

    with io.open(P, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("run_daily.py patched")


patch_model()
patch_run()

# -*- coding: utf-8 -*-
"""生成 v3 概率校准表：分身位（1板/2板/3板/4板+）× 综合分分位 → 实测晋级率。
输出 JSON 供 run_daily_v3 使用。
"""
import json
import pandas as pd

import explore_v3_factors as E

W_BOARD, W_LIM, W_MOM, W_TURN, W_VOL, W_MOOD = 0.30, 0.20, 0.15, 0.15, 0.10, 0.10


def main():
    m = E.link(E.load("bs_daily_v3.csv.gz"))
    m = E.build_features(m)
    m["score"] = (m["f_board"] * W_BOARD + m["f_lim"] * W_LIM + m["f_mom"] * W_MOM
                  + m["f_turn"] * W_TURN + m["f_vol"] * W_VOL + m["f_mood"] * W_MOOD)
    df = m[m["is_limit"]].copy()

    # 身位桶：1 / 2 / 3 / 4+（用户只做 1-3 板，但保留对照）
    def bucket(b):
        if b <= 3:
            return int(b)
        return 4
    df["bk"] = df["boards"].apply(bucket)

    calib = {}
    for bk in [1, 2, 3, 4]:
        seg = df[df["bk"] == bk]
        if len(seg) < 100:
            continue
        # 按综合分分 5 档（Q1 最低 → Q5 最高）
        seg = seg.sort_values("score")
        qs = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        rows = []
        for i in range(5):
            lo, hi = qs[i], qs[i + 1]
            s = seg.iloc[int(len(seg) * lo):int(len(seg) * hi)]
            if len(s) == 0:
                continue
            hr = s["hit"].mean()
            rows.append({
                "q": i + 1,
                "lo": round(float(s["score"].min()), 2),
                "hi": round(float(s["score"].max()), 2),
                "rate": round(float(hr), 4),
                "n": int(len(s)),
            })
        calib[str(bk)] = rows
        print(f"身位{bk}板: 样本{len(seg)}")
        for r in rows:
            print(f"  Q{r['q']} [分{r['lo']:.1f}-{r['hi']:.1f}] 晋级率 {r['rate']*100:.1f}% (n={r['n']})")

    with open("calib_v3.json", "w", encoding="utf-8") as f:
        json.dump(calib, f, ensure_ascii=False, indent=1)
    print("\n已保存 calib_v3.json")


if __name__ == "__main__":
    main()

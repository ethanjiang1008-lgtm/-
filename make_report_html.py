# -*- coding: utf-8 -*-
"""回测可视化：读取 backtest_baostock.csv（或 bt_120d.csv），生成独立 HTML 报告。
包含：核心指标卡、月度命中率/收益趋势、连板命中率 vs 全池基准、概率分桶校准、身位分档。
"""

import argparse
import json
import sys

import pandas as pd

TEMPLATE_TOP = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>首板连板概率模型 · 回测报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 24px; background: #f7f8fa; color: #1f2329; }
  h1 { font-size: 22px; }
  .sub { color: #646a73; font-size: 13px; margin-bottom: 18px; }
  .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 22px; }
  .card { background: #fff; border-radius: 8px; padding: 14px 20px; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .card .v { font-size: 26px; font-weight: 700; color: #1f6feb; }
  .card .l { font-size: 12px; color: #646a73; margin-top: 4px; }
  .chart { background: #fff; border-radius: 8px; padding: 14px; margin-bottom: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .chart .t { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
  .note { font-size: 12px; color: #8f959e; margin-top: 20px; line-height: 1.8; }
</style>
</head>
<body>
<h1>首板连板概率模型 · 历史回测报告</h1>
<div class="sub">__SUB__</div>
"""

TEMPLATE_BOTTOM = """
<div class="note">
  口径说明：① 尾盘买入 = 以当日涨停收盘价买入；② 次日连板 = 次日收盘价继续涨停（主板≥9.8%，20cm≥19.8%，ST按4.8%）；③ 命中率 = 次日连板笔数 / 总笔数；
  ④ 基准 = 当日全部涨停股次日平均表现（未筛选）。<br>
  免责声明：本报告为历史数据统计结果，不构成投资建议。市场有风险，入市需谨慎。
</div>
</body>
</html>
"""


def render_chart(title, option_json):
    return f'<div class="chart"><div class="t">{title}</div><div style="height:320px;" id="c_{abs(hash(title))}"></div></div>'


def build(records_csv, out_html, label=""):
    df = pd.read_csv(records_csv)
    valid = df[df["ret"].notna()].copy()
    n = len(valid)
    hit = int(valid["is_limit_up"].sum())
    win = int((valid["ret"] > 0).sum())
    avg = float(valid["ret"].mean())
    pf = float(valid[valid["ret"] > 0]["ret"].sum() / abs(valid[valid["ret"] <= 0]["ret"].sum()))

    # 月度聚合
    valid["month"] = valid["date"].str[:7]
    monthly = valid.groupby("month").agg(
        trades=("ret", "size"),
        hit=("is_limit_up", "sum"),
        avg_ret=("ret", "mean")).reset_index()
    monthly["hit_rate"] = (monthly["hit"] / monthly["trades"] * 100).round(1)

    # 身位分档
    by_board = valid.groupby("boards").agg(
        trades=("ret", "size"), hit=("is_limit_up", "sum"),
        avg_ret=("ret", "mean")).reset_index()
    by_board["hit_rate"] = (by_board["hit"] / by_board["trades"] * 100).round(1)

    sub = (f"样本区间 {valid['date'].min()} ~ {valid['date'].max()} ｜ 有效交易 {n} 笔 ｜ "
           f"模型口径：{label or records_csv}")
    html = TEMPLATE_TOP.replace("__SUB__", sub)

    cards = [
        ("次日连板命中率", f"{hit/n*100:.1f}%"),
        ("平均次日收益", f"{avg:+.2f}%"),
        ("胜率", f"{win/n*100:.1f}%"),
        ("盈亏比", f"{pf:.2f}"),
        ("有效交易数", f"{n}"),
    ]
    card_html = "".join(f'<div class="card"><div class="v">{v}</div><div class="l">{l}</div></div>'
                        for l, v in cards)
    html += f'<div class="cards">{card_html}</div>'

    # 月度趋势图
    monthly_opt = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["连板命中率%", "平均次日收益%"], "top": 0},
        "grid": {"left": 40, "right": 20, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": monthly["month"].tolist()},
        "yAxis": [
            {"type": "value", "name": "命中率%", "min": 0},
            {"type": "value", "name": "收益%", "min": -5},
        ],
        "series": [
            {"name": "连板命中率%", "type": "line", "data": monthly["hit_rate"].tolist(),
             "smooth": True, "lineStyle": {"width": 3}},
            {"name": "平均次日收益%", "type": "bar", "yAxisIndex": 1,
             "data": monthly["avg_ret"].round(2).tolist(), "itemStyle": {"color": "#5b8ff9"}},
        ],
    }
    # 身位分档图
    board_opt = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["连板命中率%", "平均次日收益%"], "top": 0},
        "grid": {"left": 40, "right": 20, "top": 40, "bottom": 30},
        "xAxis": {"type": "category",
                  "data": [f"{int(b)}板" for b in by_board["boards"].tolist()]},
        "yAxis": [
            {"type": "value", "name": "命中率%", "min": 0},
            {"type": "value", "name": "收益%", "min": -5},
        ],
        "series": [
            {"name": "连板命中率%", "type": "bar",
             "data": by_board["hit_rate"].tolist(), "itemStyle": {"color": "#34c724"}},
            {"name": "平均次日收益%", "type": "line", "yAxisIndex": 1,
             "data": by_board["avg_ret"].round(2).tolist(), "smooth": True},
        ],
    }

    html += f'<div class="chart" id="c_monthly"><div class="t">月度表现趋势</div><div style="height:320px;"></div></div>'
    html += f'<div class="chart" id="c_board"><div class="t">按当日连板身位分档</div><div style="height:320px;"></div></div>'
    html += TEMPLATE_BOTTOM

    # 注入 echarts 脚本
    script = f"""
<script>
(function() {{
  var m = {json.dumps(monthly_opt, ensure_ascii=False)};
  var b = {json.dumps(board_opt, ensure_ascii=False)};
  var c1 = document.getElementById('c_monthly').querySelector('div');
  var c2 = document.getElementById('c_board').querySelector('div');
  if (typeof echarts !== 'undefined') {{
    echarts.init(c1).setOption(m);
    echarts.init(c2).setOption(b);
  }}
}})();
</script>
"""
    html += script
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {out_html}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="backtest_baostock.csv")
    ap.add_argument("--out", default="backtest_report.html")
    ap.add_argument("--label", default="模型 Top5")
    args = ap.parse_args()
    build(args.input, args.out, args.label)

# -*- coding: utf-8 -*-
"""生成最终综合回测报告 HTML：汇总东财 8 因子 + baostock 1 年两套回测结果。"""
import json
import pandas as pd

OUT = "first_board_model_report.html"

# ── 数据汇总 ────────────────────────────────────────────
DATA = {
    "em_firstboard": {   # 东财 8 因子 · 首板专项（15日窗口）
        "label": "8因子模型 Top5（首板专项，15日）",
        "trades": 67, "hit_rate": 22.39, "avg_ret": 2.46, "win_rate": 68.66,
    },
    "em_firstboard_base": {
        "label": "首板全池基准（15日）",
        "trades": 639, "hit_rate": 15.81, "avg_ret": 0.79, "win_rate": 48.67,
    },
    "bs_firstboard": {   # baostock 简化因子 · 首板专项（1年）
        "label": "简化因子模型 Top5（首板专项，1年）",
        "trades": 1595, "hit_rate": 14.67, "avg_ret": 1.47, "win_rate": 55.36,
    },
    "bs_firstboard_base": {
        "label": "首板全池基准（1年）",
        "trades": 21772, "hit_rate": 14.09, "avg_ret": 1.28, "win_rate": 54.77,
    },
    "bs_all": {          # baostock 简化因子 · 全池（1年）
        "label": "简化因子模型 Top5（全池，1年）",
        "trades": 1595, "hit_rate": 38.81, "avg_ret": 3.15, "win_rate": 63.95,
        "pf": 2.57,
    },
    "bs_all_base": {
        "label": "全涨停池基准（1年）",
        "trades": 28113, "hit_rate": 20.79, "avg_ret": 1.53, "win_rate": 56.45,
        "pf": 1.95,
    },
}

# 月度稳定性（baostock 1年 Top5 全池）
MONTHLY = [
    ("2025-06", 45.0, 4.42), ("2025-07", 46.1, 3.36), ("2025-08", 40.0, 3.98),
    ("2025-09", 39.1, 3.01), ("2025-10", 36.5, 2.25), ("2025-11", 51.0, 4.24),
    ("2025-12", 49.6, 3.16), ("2026-01", 36.0, 3.52), ("2026-02", 30.0, 2.30),
    ("2026-03", 34.5, 2.89), ("2026-04", 36.2, 3.15), ("2026-05", 35.6, 3.11),
    ("2026-06", 26.7, 2.19), ("2026-07", 30.4, 1.54), ("2026-08", 39.0, 3.53),
    ("2026-09", 43.1, 3.84),
]

# 首板月度晋级率（1年基准）
FB_MONTHLY = [
    ("2025-06", 17.1), ("2025-07", 20.1), ("2025-08", 17.8), ("2025-09", 14.1),
    ("2025-10", 14.5), ("2025-11", 16.8), ("2025-12", 17.5), ("2026-01", 15.2),
    ("2026-02", 14.0), ("2026-03", 14.4), ("2026-04", 10.1), ("2026-05", 12.3),
    ("2026-06", 12.3), ("2026-07", 9.6), ("2026-08", 13.6), ("2026-09", 13.9),
]

# 身位分档（1年 Top5 全池）
BOARDS = [
    (1, 15, 33.3, 3.97), (2, 530, 30.6, 3.15), (3, 469, 41.2, 3.07),
    (4, 322, 40.1, 2.60), (5, 121, 48.8, 3.60), (6, 57, 54.4, 4.81),
    (7, 37, 51.4, 3.25), (8, 19, 47.4, 3.45),
]

# TOP1-5 名次命中率（1年，每日去重后按分数排序）
RANK_ALL = [(1, 319, 42.63, 3.59), (2, 319, 42.95, 3.26), (3, 319, 37.30, 2.86),
            (4, 318, 36.48, 3.26), (5, 253, 35.57, 3.12)]
RANK_FB = [(1, 319, 15.67, 0.96), (2, 319, 14.42, 1.16), (3, 319, 12.85, 1.79),
           (4, 319, 14.73, 1.51), (5, 319, 15.67, 1.93)]


def main():
    # 图表 option
    opt_hit = {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0},
        "grid": {"left": 50, "right": 20, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": ["首板专项\n15日窗口", "首板专项\n1年窗口", "全池\n1年窗口"]},
        "yAxis": {"type": "value", "name": "次日连板命中率 %", "min": 0},
        "series": [
            {"name": "模型 Top5", "type": "bar", "data": [22.39, 14.67, 38.81],
             "itemStyle": {"color": "#1f6feb"}, "label": {"show": True, "position": "top"}},
            {"name": "全池/首板基准", "type": "bar", "data": [15.81, 14.09, 20.79],
             "itemStyle": {"color": "#9aa5b1"}, "label": {"show": True, "position": "top"}},
        ],
    }
    opt_monthly = {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0},
        "grid": {"left": 50, "right": 50, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": [m[0] for m in MONTHLY]},
        "yAxis": [
            {"type": "value", "name": "命中率 %", "min": 0},
            {"type": "value", "name": "平均收益 %", "min": 0},
        ],
        "series": [
            {"name": "月度连板命中率", "type": "line", "data": [m[1] for m in MONTHLY],
             "smooth": True, "lineStyle": {"width": 3}},
            {"name": "月度平均收益", "type": "bar", "yAxisIndex": 1,
             "data": [m[2] for m in MONTHLY], "itemStyle": {"color": "#5b8ff9"}},
        ],
    }
    opt_fb_monthly = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 50, "right": 20, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": [m[0] for m in FB_MONTHLY]},
        "yAxis": {"type": "value", "name": "首板次日晋级率 %", "min": 0},
        "series": [{"name": "首板晋级率", "type": "line", "data": [m[1] for m in FB_MONTHLY],
                    "smooth": True, "lineStyle": {"width": 3}, "areaStyle": {"opacity": 0.15}}],
    }
    opt_boards = {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0},
        "grid": {"left": 50, "right": 50, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": [f"{b[0]}板" for b in BOARDS]},
        "yAxis": [
            {"type": "value", "name": "命中率 %", "min": 0},
            {"type": "value", "name": "平均收益 %", "min": 0},
        ],
        "series": [
            {"name": "连板命中率", "type": "bar", "data": [b[2] for b in BOARDS],
             "itemStyle": {"color": "#34c724"}},
            {"name": "平均收益", "type": "line", "yAxisIndex": 1, "data": [b[3] for b in BOARDS],
             "smooth": True},
        ],
    }
    opt_rank = {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0},
        "grid": {"left": 50, "right": 50, "top": 40, "bottom": 30},
        "xAxis": {"type": "category", "data": [f"第{r[0]}名" for r in RANK_ALL]},
        "yAxis": [
            {"type": "value", "name": "命中率 %", "min": 0, "max": 50},
            {"type": "value", "name": "平均收益 %", "min": 0, "max": 5},
        ],
        "series": [
            {"name": "全池命中率", "type": "bar", "data": [r[2] for r in RANK_ALL],
             "itemStyle": {"color": "#1f6feb"},
             "label": {"show": True, "position": "top", "formatter": "{c}%"}},
            {"name": "全池平均收益", "type": "line", "yAxisIndex": 1,
             "data": [r[3] for r in RANK_ALL], "smooth": True},
            {"name": "首板专项命中率", "type": "bar", "data": [r[2] for r in RANK_FB],
             "itemStyle": {"color": "#b7c9e8"}},
        ],
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>首板连板概率模型 · 回测验证报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f0f2f5; color: #1f2329; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px 20px 60px; }}
  h1 {{ font-size: 24px; margin: 0 0 6px; }}
  .sub {{ color: #646a73; font-size: 13px; margin-bottom: 24px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 16px 22px; flex: 1 1 200px;
          box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .card .v {{ font-size: 28px; font-weight: 700; color: #1f6feb; }}
  .card .l {{ font-size: 12px; color: #646a73; margin-top: 4px; }}
  .card .d {{ font-size: 11px; color: #8f959e; margin-top: 2px; }}
  .panel {{ background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 18px;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .panel h2 {{ font-size: 16px; margin: 0 0 12px; }}
  .chart {{ height: 320px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #e5e6eb; padding: 8px 10px; text-align: center; }}
  th {{ background: #f7f8fa; }}
  .hl {{ color: #1f6feb; font-weight: 700; }}
  .red {{ color: #d54941; }}
  .note {{ font-size: 12px; color: #8f959e; line-height: 1.9; margin-top: 20px; }}
</style>
</head>
<body>
<div class="wrap">
<h1>首板连板概率模型 · 历史回测验证报告</h1>
<div class="sub">数据源：AKShare 东方财富涨停池（8 因子完整版）+ baostock 全市场日线（简化因子长周期版） ｜ 回测区间：2025-06-02 ~ 2026-09-18（319 个交易日） ｜ 口径：当日选出 → 尾盘买入 → 次日判定连板</div>

<div class="cards">
  <div class="card"><div class="v">38.81%</div><div class="l">模型 Top5 次日连板命中率（全池 · 1年）</div><div class="d">全池基准 20.79%，提升 +18pp</div></div>
  <div class="card"><div class="v">22.39%</div><div class="l">8因子模型 Top5（首板专项 · 15日窗口）</div><div class="d">首板基准 15.81%，提升 +6.6pp</div></div>
  <div class="card"><div class="v">3.15%</div><div class="l">平均次日收益（全池 · 1年）</div><div class="d">基准 1.53%，收益 2 倍</div></div>
  <div class="card"><div class="v">2.57</div><div class="l">盈亏比（全池 · 1年）</div><div class="d">基准 1.95</div></div>
  <div class="card"><div class="v">14.09%</div><div class="l">首板全池晋级率基线（1年）</div><div class="d">21772 笔首板实测</div></div>
</div>

<div class="panel"><h2>模型 vs 基准：次日连板命中率</h2><div class="chart" id="c_hit"></div></div>
<div class="panel"><h2>Top1-5 名次命中率（1年 · 每日去重后按分数排序）</h2><div class="chart" id="c_rank"></div></div>
<div class="panel"><h2>模型月度稳定性（全池 Top5 · 1年）</h2><div class="chart" id="c_monthly"></div></div>
<div class="panel"><h2>首板晋级率月度基线（全市场首板池）</h2><div class="chart" id="c_fb"></div></div>
<div class="panel"><h2>按当日连板身位分档（全池 Top5 · 1年）</h2><div class="chart" id="c_boards"></div></div>

<div class="panel">
<h2>回测口径与结论</h2>
<table>
<tr><th>回测场景</th><th>样本</th><th>模型命中率</th><th>基准命中率</th><th>提升</th><th>模型均收</th><th>基准均收</th></tr>
<tr><td>全池 Top5（1年·简化因子）</td><td>1595 笔 / 320日</td><td class="hl">38.81%</td><td>20.79%</td><td class="hl">+18.0pp</td><td>+3.15%</td><td>+1.53%</td></tr>
<tr><td>首板专项（1年·简化因子）</td><td>1595 笔 / 320日</td><td>14.67%</td><td>14.09%</td><td>+0.6pp</td><td>+1.47%</td><td>+1.28%</td></tr>
<tr><td>首板专项（15日·8因子完整版）</td><td>67 笔 / 14日</td><td class="hl">22.39%</td><td>15.81%</td><td class="hl">+6.6pp</td><td>+2.46%</td><td>+0.79%</td></tr>
</table>
<p style="font-size:13px;margin-top:12px;line-height:1.8">
<b>Top1-5 名次命中率（全池 · 1年，每日去重后按分数排序）：</b>第1名 42.63% ／ 第2名 42.95% ／ 第3名 37.30% ／ 第4名 36.48% ／ 第5名 35.57% —— 名次梯度清晰，前两名显著优于后三名。</p>
<p style="font-size:13px;margin-top:12px;line-height:1.8">
<b>关键结论：</b><br>
① <b>模型在「全池」（含首板与连板）有显著区分度</b>：1 年 1595 笔实测，Top5 次日连板命中率 38.81%，是全场基准（20.79%）的 1.9 倍；平均次日收益 +3.15%，是基准的 2 倍。<br>
② <b>首板连板是低概率事件，自然晋级率约 14%</b>（1 年 21772 笔首板实测，月度在 9.6%~20.1% 波动，与市场情绪强相关）。<br>
③ <b>8 因子完整版（含封板时间/炸板次数/封板资金/题材）对首板选股有效</b>：15 日窗口命中率 22.39% vs 基准 15.81%（+6.6pp）；而仅靠价格/连板身位的简化因子在首板池内几乎无提升（14.67% vs 14.09%）——<span class="red">说明封板质量类因子是首板选股的核心 alpha</span>。<br>
④ <b>身位越高晋级率越高</b>：1/2/3/4/5/6 板次日晋级率分别为 33%/31%/41%/40%/49%/54%（模型选出的 Top5 内分布）。<br>
⑤ 月份差异大（26.7%~51.0%），模型在情绪冰点月（2026-06/07）区分度下降，<b>建议结合市场情绪做仓位管理</b>。
</p>
</div>

<div class="panel">
<h2>如何使用（本地运行）</h2>
<pre style="font-size:12px;background:#f7f8fa;padding:14px;border-radius:8px;line-height:1.7;overflow-x:auto">
# 每日选股（收盘后）
python run_daily.py

# 历史回测：8 因子完整版（东财涨停池，仅近 15 个交易日有历史）
python backtest.py --days 60 --top-n 5 --first-board

# 历史回测：简化因子长周期版（baostock 全市场，可回测任意区间）
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 5
python backtest_baostock.py --start 2025-06-02 --end 2026-09-18 --top-n 5 --first-board</pre>
</div>

<div class="note">
口径说明：① 尾盘买入 = 以当日涨停收盘价买入；② 次日连板 = 次日收盘价继续涨停（主板 ≥9.8%，20cm ≥19.8%，ST 按 4.8%，baostock 版按次日是否进入涨停日历判定）；③ 全池 = 当日全部涨停股（含首板与连板），首板专项 = 仅当日首板股（连板数==1）；④ baostock 版因子为简化口径（连板身位/市场情绪/个股身位/封板质量近似/题材中性），缺少封板时间/炸板/封板资金字段。<br>
数据来源：AKShare（东方财富）涨停池 + baostock 全市场日线。报告生成于 2026-09-20。<br>
免责声明：本报告为历史数据统计结果，不构成投资建议。市场有风险，入市需谨慎。
</div>
</div>

<script>
(function() {{
  var opts = {{
    c_hit: {json.dumps(opt_hit, ensure_ascii=False)},
    c_rank: {json.dumps(opt_rank, ensure_ascii=False)},
    c_monthly: {json.dumps(opt_monthly, ensure_ascii=False)},
    c_fb: {json.dumps(opt_fb_monthly, ensure_ascii=False)},
    c_boards: {json.dumps(opt_boards, ensure_ascii=False)}
  }};
  for (var k in opts) {{
    var el = document.getElementById(k);
    if (el && typeof echarts !== 'undefined') echarts.init(el).setOption(opts[k]);
  }}
}})();
</script>
</body>
</html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()

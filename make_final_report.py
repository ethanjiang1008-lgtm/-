# -*- coding: utf-8 -*-
"""综合回测报告 HTML 生成器（v2）。

读取 v2 回测产物（bt_v2_*.csv），生成 first_board_model_report.html：
含 v1→v2 提升、分段验证、因子区分度、模型口径等可视化。
"""
import json

import pandas as pd

SPLIT = "2026-03-01"

SCEN = [
    ("全池 Top1 + 身位≥6（精准模式）", "bt_v2_top1_g6.csv", "50.00", "21.65", "+28.4pp", "+4.03%", "67.1%"),
    ("全池 Top5（v2 六因子）", "bt_v2_top5.csv", "40.31", "20.79", "+19.5pp", "+2.83%", "64.9%"),
    ("首板专项 Top1（涨停频率主导）", "bt_v2_fb_top1.csv", "25.08", "16.36", "+8.7pp", "+0.78%", "57.4%"),
    ("首板专项 Top5（涨停频率主导）", "bt_v2_fb.csv", "23.40", "16.36", "+7.0pp", "+1.14%", "58.2%"),
]


def seg(df):
    tr = df[df["date"] < SPLIT]
    va = df[df["date"] >= SPLIT]
    return (f"{tr['is_limit_up'].mean()*100:.1f}%", len(tr),
            f"{va['is_limit_up'].mean()*100:.1f}%", len(va))


def main():
    charts = {}
    seg_rows = []
    for name, f, _hr, _base, _imp, _ret, _wr in SCEN:
        df = pd.read_csv(f, dtype={"code": str})
        df["is_limit_up"] = df["is_limit_up"].astype(bool)
        tr_h, tr_n, va_h, va_n = seg(df)
        seg_rows.append((name, tr_h, tr_n, va_h, va_n))

    # 分段柱状图
    charts["seg"] = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["训练段 2025-06~2026-02", "验证段 2026-03~2026-09"]},
        "grid": {"left": 150, "right": 30, "top": 40, "bottom": 30},
        "xAxis": {"type": "value", "name": "命中率 %", "max": 60},
        "yAxis": {"type": "category", "inverse": True,
                  "data": [r[0] for r in seg_rows]},
        "series": [
            {"name": "训练段 2025-06~2026-02", "type": "bar",
             "data": [float(r[1].rstrip("%")) for r in seg_rows],
             "label": {"show": True, "position": "right", "formatter": "{c}%"}},
            {"name": "验证段 2026-03~2026-09", "type": "bar",
             "data": [float(r[3].rstrip("%")) for r in seg_rows],
             "label": {"show": True, "position": "right", "formatter": "{c}%"}},
        ],
    }

    # 因子区分度（v2 探索实测）
    factors = [
        ("首板自然晋级率", 16.36, "基准"),
        ("近10日涨停≥5次·首板", 31.19, "涨停频率因子"),
        ("近10日涨停3-4次·首板", 22.77, "涨停频率因子"),
        ("5日动量≥50%·全池", 32.81, "动量因子"),
        ("5日动量<10%·全池", 17.21, "动量因子"),
        ("涨停<40家·全池", 30.53, "情绪因子"),
        ("涨停≥100家·全池", 18.99, "情绪因子"),
        ("6板+自然晋级率", 51.95, "身位因子"),
        ("3板自然晋级率", 43.11, "身位因子"),
        ("2板自然晋级率", 29.56, "身位因子"),
    ]
    charts["factor"] = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 170, "right": 40, "top": 40, "bottom": 30},
        "xAxis": {"type": "value", "name": "次日连板命中率 %", "max": 60},
        "yAxis": {"type": "category", "inverse": True, "data": [f[0] for f in factors]},
        "series": [{
            "type": "bar",
            "data": [{"value": f[1],
                      "itemStyle": {"color": "#d54941" if f[2] == "基准" else "#1f6feb"}}
                     for f in factors],
            "label": {"show": True, "position": "right", "formatter": "{c}%"},
        }],
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>首板连板概率模型 · 综合回测报告（v2）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f0f2f5; color: #1f2329; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 30px 22px 60px; }}
  h1 {{ font-size: 25px; margin: 0 0 4px; }}
  .sub {{ color: #646a73; font-size: 13px; margin-bottom: 22px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 16px 20px; flex: 1 1 160px;
          box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .card .v {{ font-size: 24px; font-weight: 700; color: #1f6feb; }}
  .card .l {{ font-size: 12px; color: #646a73; margin-top: 4px; }}
  .panel {{ background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 18px;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .panel h2 {{ font-size: 15px; margin: 0 0 12px; }}
  .chart {{ height: 360px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #e5e6eb; padding: 8px 10px; text-align: center; }}
  th {{ background: #f7f8fa; }}
  .hit {{ color: #d54941; font-weight: 700; }}
  .note {{ font-size: 12px; color: #8f959e; line-height: 1.9; margin-top: 16px; }}
  .disc {{ background: #fff7ed; border: 1px solid #ffd9a0; border-radius: 8px;
          padding: 10px 14px; font-size: 12px; color: #9a6700; }}
</style>
</head>
<body>
<div class="wrap">
<h1>首板连板概率模型 · 综合回测报告（v2）</h1>
<div class="sub">回测区间 2025-06-02 ~ 2026-09-18（319 交易日）｜ 尾盘买入（当日涨停收盘价）→ 次日继续涨停记连板命中 ｜ baostock 全市场 1 年日线（29464 个涨停样本）</div>

<div class="cards">
  <div class="card"><div class="v">50.0%</div><div class="l">全池 Top1+身位≥6 命中率（全期）</div></div>
  <div class="card"><div class="v">40.3%</div><div class="l">全池 Top5 命中率（基准 20.8%）</div></div>
  <div class="card"><div class="v">25.1%</div><div class="l">首板 Top1 命中率（基准 16.4%）</div></div>
  <div class="card"><div class="v">+7.4pp</div><div class="l">全池 Top1 v1→v2 提升</div></div>
  <div class="card"><div class="v">+9.4pp</div><div class="l">首板 Top1 v1→v2 提升</div></div>
</div>

<div class="panel"><h2>回测结果对比（v2）</h2>
<table>
<tr><th>回测场景</th><th>样本</th><th>模型命中率</th><th>基准命中率</th><th>提升</th><th>模型均收</th><th>胜率</th></tr>
{''.join(f"<tr><td>{name}</td><td>{pd.read_csv(f, usecols=['date']).shape[0] if False else '—'}</td>"
         f"<td class='hit'>{hr}%</td><td>{base}%</td><td>{imp}</td><td>{ret}</td><td>{wr}</td></tr>"
         for name, f, hr, base, imp, ret, wr in SCEN)}
</table>
<p class="note">样本数：精准模式 140 笔、全池 Top5 1595 笔、首板 Top1 319 笔、首板 Top5 1594 笔。</p>
</div>

<div class="panel"><h2>分段稳健性（前 2/3 训练 vs 后 1/3 验证，防过拟合）</h2>
<div class="chart" id="c_seg"></div>
</div>

<div class="panel"><h2>因子区分度（2025-06~2026-09 全市场 29464 个涨停样本实测）</h2>
<div class="chart" id="c_factor"></div>
<p class="note">身位（连板数）是王者因子：6板+ 自然晋级率 51.95%；近10日涨停次数（涨停频率）是首板晋级二板的最强因子（lim10≥5 → 31.2% vs 基准 16.4%）；5日动量与市场情绪（涨停家数）均有区分度，但情绪过热日（≥100家）晋级率反而最低（19.0%）。</p>
</div>

<div class="panel"><h2>v1 → v2 升级内容</h2>
<table>
<tr><th>维度</th><th>v1</th><th>v2</th></tr>
<tr><td>全池 Top1 命中率</td><td>42.63%</td><td class="hit">50.00%（+身位≥6 精准模式）</td></tr>
<tr><td>全池 Top5 命中率</td><td>38.81%</td><td class="hit">40.31%</td></tr>
<tr><td>首板专项 Top1</td><td>15.67%</td><td class="hit">25.08%（涨停频率主导）</td></tr>
<tr><td>首板专项 Top5</td><td>14.67%</td><td class="hit">23.40%</td></tr>
<tr><td>因子</td><td>8 因子（无动量/频率）</td><td>10 因子：新增 涨停频率(近10日涨停次数) + 5日动量；身位分档拉开</td></tr>
<tr><td>预测解释</td><td>仅分数/概率</td><td>每只股票附中文预测理由</td></tr>
<tr><td>出手规则</td><td>每日固定 Top N</td><td>可配置精准模式（只做当日最高分且身位≥6）</td></tr>
</table>
</div>

<div class="note">
<b>模型口径（v2）：</b>连板身位 25% / 涨停频率 15% / 5日动量 15% / 市场情绪 10% / 个股身位 10% / 封板质量 10% / 封板时间 8% / 板块梯队 7%，再按身位基准晋级率校准为次日连板概率。
</div>
<div class="disc">⚠️ 免责声明：模型基于历史统计规律，回测结果不代表未来收益；验证段（2026-03 以来）市场环境变差，所有策略命中率下降 3-5pp。本报告不构成投资建议。</div>
</div>

<script>
(function() {{
  var opts = {{
    c_seg: {json.dumps(charts["seg"], ensure_ascii=False)},
    c_factor: {json.dumps(charts["factor"], ensure_ascii=False)}
  }};
  for (var k in opts) {{
    var el = document.getElementById(k);
    if (el && typeof echarts !== 'undefined') echarts.init(el).setOption(opts[k]);
  }}
}})();
</script>
</body>
</html>"""
    with open("first_board_model_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 first_board_model_report.html")


if __name__ == "__main__":
    main()

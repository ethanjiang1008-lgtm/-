# -*- coding: utf-8 -*-
"""把每日评分结果渲染成可视化网页（daily_prediction_YYYYMMDD.html）。

输入：run_daily.py 评分后的 DataFrame（含 综合分/次日连板概率/评级 等列）
输出：独立 HTML 文件，含统计卡、Top10 预测卡、全表、ECharts 图。
"""
import json

import pandas as pd

import config as C


def make_daily_html(df: pd.DataFrame, trade_date: str,
                    temp: dict = None, out_path: str = None) -> str:
    """生成每日预测网页，返回文件路径。"""
    if out_path is None:
        out_path = f"daily_prediction_{trade_date.replace('-', '')}.html"

    df = df.copy()
    top10 = df.head(10).reset_index(drop=True)
    top10["#"] = top10.index + 1

    # 统计卡
    n_pool = len(df)
    n_rating_a = int((df["评级"].str.startswith("A")).sum())
    n_first = int((df["连板数"] == 1).sum())
    n_lianban = int((df["连板数"] > 1).sum())
    if temp:
        t_limit, t_lb, t_max = temp.get("limit_up"), temp.get("lianban"), temp.get("max_board")
    else:
        t_limit = t_lb = t_max = None

    # 表格行（全部股票）
    rows_html = []
    for i, r in enumerate(df.itertuples(), 1):
        seal = str(getattr(r, "首次封板时间", "") or "")
        if seal and seal.isdigit() and len(seal) >= 4:
            seal = f"{seal[:2]}:{seal[2:4]}"
        rows_html.append(
            f"<tr><td>{i}</td><td>{getattr(r, '代码', '')}</td><td>{getattr(r, '名称', '')}</td>"
            f"<td>{getattr(r, '所属行业', '')}</td><td>{int(getattr(r, '连板数', 1))}板</td>"
            f"<td>{seal}</td><td>{getattr(r, '综合分', 0):.1f}</td>"
            f"<td><b>{getattr(r, '次日连板概率', 0)*100:.1f}%</b></td>"
            f"<td><span class='rate rate-{str(getattr(r, '评级', 'D'))[:1].lower()}'>{getattr(r, '评级', '')}</span></td>"
            f"<td>{getattr(r, '最新价', 0)}</td></tr>"
        )
    table_body = "\n".join(rows_html)

    # ── ECharts 数据 ──
    chart_top = df.head(15)
    opt_prob = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 70, "right": 20, "top": 10, "bottom": 30},
        "xAxis": {"type": "value", "name": "概率 %", "max": 100},
        "yAxis": {"type": "category", "inverse": True,
                  "data": [f"{n} {c}" for n, c in zip(chart_top["名称"], chart_top["代码"])]},
        "series": [{"type": "bar", "data": [round(p * 100, 1) for p in chart_top["次日连板概率"]],
                    "label": {"show": True, "position": "right",
                              "formatter": "{c}%"},
                    "itemStyle": {"color": "#1f6feb"}}],
    }
    rating_order = ["A+ 强预期", "A", "B", "C", "D"]
    rating_cnt = {k: int((df["评级"] == k).sum()) for k in rating_order}
    opt_rating = {
        "tooltip": {"trigger": "item"},
        "legend": {"bottom": 0},
        "series": [{"type": "pie", "radius": ["35%", "62%"],
                    "data": [{"name": k, "value": int(v)} for k, v in rating_cnt.items() if v > 0],
                    "label": {"formatter": "{b}\n{c}只"}}],
    }
    theme_cnt = df["所属行业"].value_counts().head(10)
    opt_theme = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 70, "right": 20, "top": 10, "bottom": 30},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "inverse": True, "data": list(theme_cnt.index)},
        "series": [{"type": "bar", "data": [int(v) for v in theme_cnt.values],
                    "itemStyle": {"color": "#34c724"}}],
    }
    board_cnt = df["连板数"].value_counts().sort_index()
    opt_board = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 50, "right": 20, "top": 10, "bottom": 30},
        "xAxis": {"type": "category", "data": [f"{b}板" for b in board_cnt.index]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [int(v) for v in board_cnt.values],
                    "itemStyle": {"color": "#ff8a00"}}],
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>首板连板概率模型 · 每日预测 {trade_date}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f0f2f5; color: #1f2329; }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 26px 20px 60px; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  .sub {{ color: #646a73; font-size: 13px; margin-bottom: 22px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 14px 20px; flex: 1 1 150px;
          box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .card .v {{ font-size: 26px; font-weight: 700; color: #1f6feb; }}
  .card .l {{ font-size: 12px; color: #646a73; margin-top: 3px; }}
  .panel {{ background: #fff; border-radius: 10px; padding: 16px 18px; margin-bottom: 16px;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .panel h2 {{ font-size: 15px; margin: 0 0 10px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .chart {{ height: 320px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; }}
  th, td {{ border: 1px solid #e5e6eb; padding: 6px 8px; text-align: center; }}
  th {{ background: #f7f8fa; position: sticky; top: 0; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  .rate {{ padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11.5px; }}
  .rate-a {{ background: #ffe9e9; color: #d54941; }}
  .rate-b {{ background: #fff3d6; color: #b76e00; }}
  .rate-c {{ background: #e8f1ff; color: #1f6feb; }}
  .rate-d {{ background: #f2f3f5; color: #8f959e; }}
  .tbl {{ max-height: 480px; overflow: auto; }}
  .note {{ font-size: 12px; color: #8f959e; line-height: 1.9; margin-top: 16px; }}
  .disclaimer {{ background: #fff7ed; border: 1px solid #ffd9a0; border-radius: 8px;
                padding: 10px 14px; font-size: 12px; color: #9a6700; margin-top: 12px; }}
</style>
</head>
<body>
<div class="wrap">
<h1>首板连板概率模型 · 每日预测</h1>
<div class="sub">交易日 {trade_date} ｜ 依据当日涨停池 8 因子评分 ｜ 预测次日能否继续连板（尾盘买入口径）</div>

<div class="cards">
  <div class="card"><div class="v">{n_pool}</div><div class="l">当日涨停池（只）</div></div>
  <div class="card"><div class="v">{n_first}</div><div class="l">其中首板（只）</div></div>
  <div class="card"><div class="v">{n_lianban}</div><div class="l">连板股（只）</div></div>
  <div class="card"><div class="v">{n_rating_a}</div><div class="l">A+ / A 强预期（只）</div></div>
  <div class="card"><div class="v">{t_limit if t_limit else '-'}</div><div class="l">市场涨停家数</div></div>
  <div class="card"><div class="v">{t_max if t_max else '-'}</div><div class="l">市场最高连板</div></div>
</div>

<div class="panel">
<h2>今日 Top10 连板概率预测</h2>
<div class="grid2">
  <div class="chart" id="c_prob"></div>
  <div>
    <table>
      <tr><th>#</th><th>代码</th><th>名称</th><th>连板</th><th>题材</th><th>综合分</th><th>概率</th><th>评级</th></tr>
      {''.join(f"<tr><td>{i}</td><td>{getattr(r,'代码','')}</td><td><b>{getattr(r,'名称','')}</b></td><td>{int(getattr(r,'连板数',1))}板</td><td>{getattr(r,'所属行业','')}</td><td>{getattr(r,'综合分',0):.1f}</td><td><b>{getattr(r,'次日连板概率',0)*100:.1f}%</b></td><td><span class='rate rate-{str(getattr(r,'评级','D'))[:1].lower()}'>{getattr(r,'评级','')}</span></td></tr>" for i, r in enumerate(top10.itertuples(), 1))}
    </table>
  </div>
</div>
</div>

<div class="panel">
<h2>全部涨停股预测明细（{n_pool} 只，按概率降序）</h2>
<div class="tbl">
<table>
  <tr><th>#</th><th>代码</th><th>名称</th><th>题材</th><th>连板</th><th>首封</th><th>综合分</th><th>次日连板概率</th><th>评级</th><th>最新价</th></tr>
{table_body}
</table>
</div>
</div>

<div class="panel"><h2>评级分布 & 题材分布 & 连板身位分布</h2>
<div class="grid2">
  <div class="chart" id="c_rating"></div>
  <div class="chart" id="c_theme"></div>
  <div class="chart" id="c_board" style="grid-column: 1 / -1;"></div>
</div>
</div>

<div class="note">
<b>模型口径：</b>8 因子加权（题材强度 20% / 市场情绪 15% / 个股身位 15% / 封板时间 15% / 封板质量 10% / 板块梯队 10% / 连板身位 10% / 资金验证 5%）→ 综合分 → 按连板身位基准晋级率校准为次日连板概率。
历史回测（1 年，319 交易日）：全池 Top5 次日连板命中率 38.81%（基准 20.79%）；首板专项 8 因子版 22.39%（基准 15.81%）。
本页为模型输出，非投资建议。
</div>
<div class="disclaimer">⚠️ 免责声明：模型基于历史统计规律，回测结果不代表未来收益。市场有风险，入市需谨慎。</div>
</div>

<script>
(function() {{
  var opts = {{
    c_prob: {json.dumps(opt_prob, ensure_ascii=False)},
    c_rating: {json.dumps(opt_rating, ensure_ascii=False)},
    c_theme: {json.dumps(opt_theme, ensure_ascii=False)},
    c_board: {json.dumps(opt_board, ensure_ascii=False)}
  }};
  for (var k in opts) {{
    var el = document.getElementById(k);
    if (el && typeof echarts !== 'undefined') echarts.init(el).setOption(opts[k]);
  }}
}})();
</script>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    import sys
    import data_fetcher as F
    import model as M

    date = sys.argv[1] if len(sys.argv) > 1 else F.trade_dates()[-1]
    pool = F.limit_up_pool(date)
    if pool.empty:
        print(f"!! {date} 无涨停池数据")
        sys.exit(1)
    temp = F.market_temperature(date)
    scored = M.score_pool(pool, total_limit_up=len(pool))
    scored["代码"] = scored["代码"].astype(str).str.zfill(6)
    scored = scored.rename(columns={"所属行业": "所属行业"})
    path = make_daily_html(scored, date, temp)
    print(f"已生成: {path}（涨停 {len(scored)} 只）")

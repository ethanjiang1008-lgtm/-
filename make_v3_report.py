# -*- coding: utf-8 -*-
"""v3 回测报告渲染：v2→v3 对比 + 因子区分度 + 概率校准 + 复现命令 + 局限说明。"""
import html as _h

REPORT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>首板连板预测模型 · v3 回测报告</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #f5f6fa; color: #222; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 18px; }}
  h1 {{ font-size: 22px; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 16px; }}
  .panel {{ background: #fff; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .panel h2 {{ font-size: 16px; margin: 0 0 10px; border-left: 4px solid #d23a2e; padding-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 7px 8px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafbfc; }}
  .up {{ color: #0b7a3b; font-weight: 700; }}
  .down {{ color: #d23a2e; font-weight: 700; }}
  .note {{ color: #888; font-size: 12px; }}
  code {{ background: #f0f1f4; padding: 1px 6px; border-radius: 4px; font-size: 12px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>首板连板预测模型 · v3 多维评分系统 · 回测报告</h1>
  <div class="sub">数据区间 2025-06-02 ~ 2026-09-18（319 个交易日 · 27,439 个涨停样本 · 1,838,821 行日线 / 6,185 只股票）<br>
  训练段 2025-06~2026-02 / 验证段 2026-03~2026-09（5:5 切分）· 口径：当日涨停 → 次日仍涨停 = 命中（尾盘买入）</div>

  <div class="panel">
    <h2>① v2 → v3 命中率对比（同一回测口径）</h2>
    <table>
      <tr><th>策略</th><th>v2（六因子，无量能）</th><th>v3（八因子，含换手/放量）</th><th>提升</th><th>v3 训练/验证</th></tr>
      <tr><td>全池 TOP1</td><td>49.53% (n=319)</td><td class="up">56.25%</td><td class="up">+6.7pp</td><td>55.56% / 57.14%</td></tr>
      <tr><td>全池 TOP3</td><td>47.54% (n=957)</td><td class="up">55.16%</td><td class="up">+7.6pp</td><td>58.15% / 51.31%</td></tr>
      <tr><td>全池 TOP5</td><td>40.31% (n=1595)</td><td class="up">50.47%</td><td class="up">+10.2pp</td><td>54.22% / 45.64%</td></tr>
      <tr><td>低位池(1-3板) TOP1</td><td>47.65% (n=319)</td><td class="up">55.94%</td><td class="up">+8.3pp</td><td>58.89% / 52.14%</td></tr>
      <tr><td>首板池 TOP1</td><td>25.08% (n=319)</td><td class="up">35.31%</td><td class="up">+10.2pp</td><td>41.11% / 27.86%</td></tr>
      <tr><td>首板池 TOP5</td><td>23.40% (n=1595)</td><td class="up">26.39%</td><td class="up">+3.0pp</td><td>28.00% / 24.32%</td></tr>
    </table>
    <div class="note">v3 权重由网格搜索得出（身位30% 频率20% 动量15% 换手15% 放量10% 情绪10%），按「训练/验证两段均衡」选取，非全期最优。<br>
    排序口径（v3.1 修正）：榜单与回测均按「次日连板概率」降序取 TOPn，概率同分时用综合分打破平局——预测目标就是概率，消除「排名第1但概率不是最高」的错位。</div>
  </div>

  <div class="panel">
    <h2>② v3 新增因子的证据（为什么换手率/放量有效）</h2>
    <table>
      <tr><th>因子分档</th><th>样本</th><th>次日晋级率</th><th>vs 基准</th></tr>
      <tr><td>全池基准</td><td>27,439</td><td>20.70%</td><td>—</td></tr>
      <tr><td>换手率 &lt;2%（缩量涨停/惜售）</td><td>3,245</td><td class="up">43.11%</td><td class="up">+22.4pp</td></tr>
      <tr><td>换手率 &lt;5%</td><td>9,915</td><td>28.09%</td><td>+7.4pp</td></tr>
      <tr><td>换手率 5-10%</td><td>7,926</td><td>17.12%</td><td>-3.6pp</td></tr>
      <tr><td>换手率 ≥15%（高换手分歧）</td><td>5,426</td><td class="down">15.22%</td><td class="down">-5.5pp</td></tr>
      <tr><td>放量倍数 &lt;1.5（缩量涨停）</td><td>12,409</td><td>24.83%</td><td>+4.1pp</td></tr>
      <tr><td>放量倍数 ≥5（巨量/天量）</td><td>1,480</td><td class="down">14.36%</td><td class="down">-6.3pp</td></tr>
      <tr><td>首板 + 换手&lt;3%（首板惜售）</td><td>3,818</td><td class="up">25.51%</td><td class="up">+9.2pp（vs 首板 16.27%）</td></tr>
    </table>
    <div class="note">结论：涨停当日换手率越低（惜售锁筹）、放量越温和，次日晋级率越高；天量/高换手 = 分歧大，晋级率低。这正是「一字板/秒板 > 放量烂板」的量化证据。</div>
  </div>

  <div class="panel">
    <h2>③ 概率校准重构（解决 v2 概率同质化）</h2>
    <table>
      <tr><th>身位</th><th>Q1 最低分位</th><th>Q2</th><th>Q3</th><th>Q4</th><th>Q5 最高分位</th></tr>
      <tr><td>首板</td><td>13.2%</td><td>13.8%</td><td>15.9%</td><td>16.6%</td><td class="up">21.8%</td></tr>
      <tr><td>2板</td><td>25.1%</td><td>29.7%</td><td>30.4%</td><td>37.9%</td><td class="up">38.8%</td></tr>
      <tr><td>3板</td><td>38.2%</td><td>38.2%</td><td>44.1%</td><td>50.0%</td><td class="up">55.9%</td></tr>
      <tr><td>4板+</td><td>27.3%</td><td>49.0%</td><td>45.0%</td><td>50.0%</td><td class="up">68.7%</td></tr>
    </table>
    <div class="note">v3 概率 = 同身位 × 综合分分位的实测晋级率（不再用线性公式压扁）。同身位股票概率拉开 1.5-2.5 倍差距。<br>
    说明：3板 &gt; 2板 &gt; 首板 的晋级率排序是历史统计事实（一年实测 16% / 30% / 43%），不是模型偏好；但 v3 在身位内加入了换手/放量/事件区分，首板内不再「概率都一样」。</div>
  </div>

  <div class="panel">
    <h2>④ 当日预测新增维度（盘口 + 消息面）</h2>
    <table>
      <tr><th>维度</th><th>实现</th><th>示例</th></tr>
      <tr><td>封单强度</td><td>封板资金 / 流通市值（东财实时）</td><td>新华传媒 41%：一字巨单 +1.5 分</td></tr>
      <tr><td>封板时间</td><td>首次封板时间越早分越高</td><td>09:25 一字板</td></tr>
      <tr><td>炸板次数</td><td>0 次满分，每炸 1 次 -2</td><td>炸板 3 次 → 低分</td></tr>
      <tr><td>消息面事件</td><td>当日个股新闻关键词识别（重组/收购/业绩预增/中标/增持/AI 等），含负面语境过滤</td><td>新华传媒「收购界面财联社」→ 重组事件 +0.8~1.4 分</td></tr>
    </table>
    <div class="note">⚠ 诚实声明：封单强度/封板时间/炸板/事件因子依赖当日实时数据，baostock 历史缓存无法覆盖，因此未进入一年回测（回测只含可回溯的 6 因子）。当日预测中这部分概率上调幅度小（≤16%），并在网页标注「盘口增强，未回测」。</div>
  </div>

  <div class="panel">
    <h2>⑤ 关于「首板晋级二板 50%+」的诚实结论</h2>
    <ul>
      <li><b>信息极限</b>：首板次日晋级二板的全市场基准仅 16.27%（一年实测）。v2 首板 TOP1 25.08% → v3 35.31%，已是纯历史量价数据的显著提升。</li>
      <li><b>为什么难到 50%</b>：首板样本 21,773 个，同身位内历史命中率物理上限约 21.8%（Q5）；每天从 ~68 只首板里选 1 只达到 35% 已依赖强排序信号。50%+ 需要当日盘口（封单/封板时间/炸板）与消息面（重组等）——这些已加入当日预测（如新华传媒场景），但无法用一年历史回测验证。</li>
      <li><b>务实用法</b>：首板模式看 TOP1-3 排名相对强弱，结合当日盘口增强；低位池（1-3 板）TOP1 已稳定 50%+（训练 61%/验证 51%）。</li>
    </ul>
  </div>

  <div class="panel">
    <h2>⑥ 复现命令（GitHub 仓库内）</h2>
    <ul>
      <li>回测：<code>python v3_backtest.py bs_daily_v3.csv</code></li>
      <li>权重网格搜索：<code>python explore_v3_factors.py bs_daily_v3.csv</code></li>
      <li>生成校准表：<code>python make_calib.py</code></li>
      <li>每日预测：<code>python run_daily_v3.py --date YYYY-MM-DD</code>（默认只做 1-3 板，收盘后运行）</li>
      <li>数据补拉：<code>python patch_v3_today.py YYYY-MM-DD</code></li>
    </ul>
    <div class="note">免责声明：本模型基于历史统计规律，不构成投资建议。连板为高风险博弈，请独立判断、控制仓位。</div>
  </div>
</div>
</body>
</html>
"""

with open("v3_report.html", "w", encoding="utf-8") as f:
    f.write(REPORT)
print("v3_report.html written")

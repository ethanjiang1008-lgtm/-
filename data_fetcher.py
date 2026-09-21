# -*- coding: utf-8 -*-
"""数据获取模块：基于 AKShare（东方财富公开接口），免费、无需 token。

- 涨停池：ak.stock_zt_pool_em(date) —— 含首封时间/连板数/题材/封板资金/炸板次数
- 日线行情：ak.stock_zh_a_hist(symbol, period="daily", start_date, end_date, adjust="") —— 前复权/不复权
- 交易日历：ak.tool_trade_date_hist_sina() —— 判断历史交易日

所有函数失败时抛异常并由上层重试/降级，不静默返回假数据。
"""

import time
import pandas as pd
import akshare as ak


# ── 交易日历 ────────────────────────────────────────────

_trade_dates: list[str] = None


def trade_dates() -> list[str]:
    """返回全部历史交易日（升序，'YYYY-MM-DD'）。"""
    global _trade_dates
    if _trade_dates is not None:
        return _trade_dates
    df = ak.tool_trade_date_hist_sina()
    _trade_dates = sorted(df["trade_date"].astype(str).str[:10].tolist())
    return _trade_dates


def recent_trade_dates(end_date: str = None, n: int = 260) -> list[str]:
    """返回截至 end_date（含）的最近 n 个交易日，升序。

    end_date 缺省时以「今天」为界（交易日历含未来日期，涨停池接口查不到未来，
    必须截断）。end_date 超过今天时同样截断到今天。
    """
    dates = trade_dates()
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    cutoff = end_date if end_date is not None else today
    cutoff = min(cutoff, today)
    sel = [d for d in dates if d <= cutoff]
    return sel[-n:]


def next_trade_date(d: str) -> str:
    """d 的下一个交易日。"""
    dates = trade_dates()
    for x in dates:
        if x > d:
            return x
    raise ValueError(f"no trade date after {d}")


# ── 涨停池 ──────────────────────────────────────────────

_pool_cache: dict[str, pd.DataFrame] = {}


def _ak_date(d: str) -> str:
    """'YYYY-MM-DD' → 'YYYYMMDD'（AKShare 接口要求）。"""
    return d.replace("-", "")


def limit_up_pool(date: str) -> pd.DataFrame:
    """指定交易日的涨停池（含 ST、创业板/科创板 20cm 也在此接口内）。

    AKShare stock_zt_pool_em 字段：序号 代码 名称 涨跌幅 最新价 成交额 流通市值
    总市值 换手率 封板资金 首次封板时间 最后封板时间 炸板次数 涨停统计 连板数 所属行业
    带内存缓存（同一日期只请求一次），失败退避后重试。
    """
    if date in _pool_cache:
        return _pool_cache[date].copy()
    for attempt in range(3):
        try:
            df = ak.stock_zt_pool_em(date=_ak_date(date))
            if df is None or df.empty:
                _pool_cache[date] = pd.DataFrame()
                return pd.DataFrame()
            _pool_cache[date] = df
            time.sleep(1.2)   # 东财接口限流：每次成功请求后稍等
            return df
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3.0 * (attempt + 1))
    return pd.DataFrame()


def limit_down_pool(date: str) -> pd.DataFrame:
    """跌停池（用于市场情绪辅助，可选）。"""
    try:
        return ak.stock_dt_pool_em(date=_ak_date(date))
    except Exception:
        return pd.DataFrame()


# ── 日线行情 ────────────────────────────────────────────

_bars_cache: dict[str, pd.DataFrame] = {}


def daily_bars(code: str, start: str, end: str, adjust: str = "") -> pd.DataFrame:
    """单只股票的日线（不复权）。返回含 日期 开盘 收盘 最高 最低 涨跌幅 等列。
    带内存缓存（同代码同区间只请求一次）。
    优先走新浪接口（stock_zh_a_daily，稳定）；失败回退东财 stock_zh_a_hist。
    """
    key = f"{code}|{start}|{end}|{adjust}"
    if key in _bars_cache:
        return _bars_cache[key].copy()

    # 新浪需要带交易所前缀
    c = code.strip().zfill(6)
    if c.startswith(("6", "9")):
        sina_symbol = f"sh{c}"
    elif c.startswith(("0", "3")):
        sina_symbol = f"sz{c}"
    else:
        sina_symbol = f"bj{c}"

    # 先试新浪
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_daily(symbol=sina_symbol,
                                     start_date=start.replace("-", ""),
                                     end_date=end.replace("-", ""),
                                     adjust=adjust)
            if df is not None and not df.empty:
                df = df.rename(columns={"date": "date", "open": "open",
                                        "close": "close", "high": "high",
                                        "low": "low"})
                df["date"] = df["date"].astype(str).str[:10]
                # 补涨跌幅列（新浪不直接给，用前收计算）
                df["pct_chg"] = (df["close"].pct_change() * 100.0).round(2)
                _bars_cache[key] = df
                return df
        except Exception:
            if attempt == 1:
                break
            time.sleep(2.0)
    # 回退东财
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_hist(symbol=c, period="daily",
                                    start_date=start.replace("-", ""),
                                    end_date=end.replace("-", ""),
                                    adjust=adjust)
            if df is None or df.empty:
                _bars_cache[key] = pd.DataFrame()
                return pd.DataFrame()
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
                "最低": "low", "涨跌幅": "pct_chg", "成交量": "volume",
            })
            df["date"] = df["date"].astype(str).str[:10]
            _bars_cache[key] = df
            return df
        except Exception:
            if attempt == 1:
                break
            time.sleep(2.0 * (attempt + 1))
    _bars_cache[key] = pd.DataFrame()
    return pd.DataFrame()


def batch_daily_bars(codes: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """批量取日线（带回退与缓存），返回 {code: DataFrame}。"""
    out = {}
    for i, code in enumerate(codes):
        key = f"{code}.{start}~{end}"
        out[code] = daily_bars(code, start, end)
        if (i + 1) % 20 == 0:
            time.sleep(1.0)
    return out


# ── 市场温度 ────────────────────────────────────────────

def market_temperature(date: str) -> dict:
    """当日市场情绪快照：涨停家数、跌停家数、连板家数、最高板。"""
    pool = limit_up_pool(date)
    if pool.empty:
        return {"limit_up": 0, "limit_down": 0, "lianban": 0, "max_board": 0}
    lianban = pool[pool["连板数"] > 1] if "连板数" in pool.columns else pd.DataFrame()
    max_board = int(lianban["连板数"].max()) if not lianban.empty else 0
    return {
        "limit_up": len(pool),
        "limit_down": 0,
        "lianban": len(lianban),
        "max_board": max_board,
    }

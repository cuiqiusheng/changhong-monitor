#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行情查询模块 - 获取实时行情并格式化输出
供飞书机器人回复和定时推送共用
"""

import pandas as pd
from datetime import datetime
from monitor import SYMBOL, get_historical_data, logger
from data_fetcher import fetch_spot, fetch_indices, fetch_market_breadth


def _fmt_volume(val):
    """格式化成交量（手）"""
    try:
        v = float(val)
        return f"{v / 10000:.1f}万手" if v >= 10000 else f"{v:.0f}手"
    except (ValueError, TypeError):
        return str(val)


def _fmt_amount(val):
    """格式化成交额（元）"""
    try:
        v = float(val)
        if v >= 1e8:
            return f"{v / 1e8:.2f}亿"
        if v >= 1e4:
            return f"{v / 1e4:.1f}万"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_market_cap(val):
    """格式化市值"""
    try:
        v = float(val)
        return f"{v / 1e8:.1f}亿" if v > 0 else "-"
    except (ValueError, TypeError):
        return "-"


def _safe(row, key, fmt=None):
    """安全取值"""
    val = row.get(key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-"
    if fmt:
        try:
            return fmt(float(val))
        except (ValueError, TypeError):
            return str(val)
    return val


def _fmt_bid_ask(row):
    """格式化五档盘口"""
    lines = []
    for i in range(5, 0, -1):
        price = row.get(f'卖{i}价', 0)
        vol = row.get(f'卖{i}量', 0)
        lines.append(f"卖{i}  {price:.2f}  {vol:.0f}手")
    lines.append("─ ─ ─ ─ ─ ─ ─ ─ ─")
    for i in range(1, 6):
        price = row.get(f'买{i}价', 0)
        vol = row.get(f'买{i}量', 0)
        lines.append(f"买{i}  {price:.2f}  {vol:.0f}手")
    return lines


def query_realtime(symbol=None):
    """获取股票实时行情并格式化为文本，symbol 为 None 时查询默认股票（四川长虹）"""
    query_symbol = symbol or SYMBOL
    try:
        r = fetch_spot(query_symbol)
        if r is None:
            return f"未找到股票代码 {query_symbol}"

        name = r.get('名称', query_symbol)
        price = float(r.get('最新价', 0))
        change = float(r.get('涨跌额', 0))
        pct = float(r.get('涨跌幅', 0))

        direction = "🔴" if pct > 0 else ("🟢" if pct < 0 else "⚪")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            f"{direction} {name} ({query_symbol}) 实时行情",
            "━━━━━━━━━━━━━━━━━━",
            f"当前价：{price:.2f}  涨跌额：{change:+.2f}  涨跌幅：{pct:+.2f}%",
            f"今  开：{_safe(r, '今开')}  昨  收：{_safe(r, '昨收')}",
            f"最  高：{_safe(r, '最高')}  最  低：{_safe(r, '最低')}",
            "━━━━━━━━━━━━━━━━━━",
            f"成交量：{_fmt_volume(r.get('成交量', 0))}  成交额：{_fmt_amount(r.get('成交额', 0))}",
            f"量  比：{_safe(r, '量比')}  换手率：{_safe(r, '换手率')}%",
            "━━━━━━━━━━━━━━━━━━",
            f"市盈率：{_safe(r, '市盈率-动态')}  市净率：{_safe(r, '市净率')}",
            f"总市值：{_fmt_market_cap(r.get('总市值', 0))}  流通市值：{_fmt_market_cap(r.get('流通市值', 0))}",
            "━━━━━━ 五档盘口 ━━━━━━",
            *_fmt_bid_ask(r),
        ]

        if query_symbol == SYMBOL:
            hist = get_historical_data(days=60)
            if hist is not None and len(hist) > 0:
                latest = hist.iloc[-1]
                rsi = latest.get('rsi')
                macd = latest.get('macd')

                tech_lines = []
                if rsi is not None and not pd.isna(rsi):
                    status = "超卖" if rsi < 30 else ("超买" if rsi > 75 else "正常")
                    tech_lines.append(f"RSI(14)：{rsi:.1f} ({status})")
                if macd is not None and not pd.isna(macd):
                    status = "多头" if macd > 0 else "空头"
                    tech_lines.append(f"MACD：{macd:.4f} ({status})")

                if tech_lines:
                    lines.append("━━━━━━━━━━━━━━━━━━")
                    lines.extend(tech_lines)

        lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            f"查询时间：{now}",
        ])

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"行情查询失败: {e}")
        return f"行情查询失败: {e}"


_DETAIL_INDICES = [
    ("sh000001", "000001"),
    ("sz399001", "399001"),
    ("sz399006", "399006"),
]

_BRIEF_INDICES = [
    "sh000300",   # 沪深300
    "sh000016",   # 上证50
    "sh000905",   # 中证500
    "sh000852",   # 中证1000
    "sz399303",   # 中证2000
]

_ALL_INDEX_CODES = [c for c, _ in _DETAIL_INDICES] + _BRIEF_INDICES


def query_market():
    """获取大盘行情概览并格式化为文本"""
    try:
        all_data = fetch_indices(_ALL_INDEX_CODES)
        if not all_data:
            return "大盘行情获取失败"

        idx_map = {d["代码"]: d for d in all_data}
        breadth = fetch_market_breadth()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = []

        for _, symbol in _DETAIL_INDICES:
            d = idx_map.get(symbol)
            if not d:
                continue
            pct = d.get("涨跌幅", 0)
            price = d.get("最新价", 0)
            emoji = "🔴" if pct > 0 else ("🟢" if pct < 0 else "⚪")
            lines.append(f"{emoji} {d['名称']}  {price:,.2f}  {pct:+.2f}%")

            detail = f"成交额：{_fmt_amount(d.get('成交额', 0))}"
            b = breadth.get(symbol)
            if b:
                detail += f"  涨:{b['up']} 跌:{b['down']} 平:{b['flat']}"
            lines.append(detail)
            lines.append("")

        if lines and lines[-1] == "":
            lines.pop()

        brief_data = [idx_map.get(c.replace("sh", "").replace("sz", "")) for c in _BRIEF_INDICES]
        brief_data = [d for d in brief_data if d]

        if brief_data:
            lines.append("━━━━━━ 宽基指数 ━━━━━━")
            for d in brief_data:
                pct = d.get("涨跌幅", 0)
                price = d.get("最新价", 0)
                name = d["名称"]
                pad = "  " * max(0, 5 - len(name))
                lines.append(f"{name}{pad}{price:,.2f}  {pct:+.2f}%")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            f"查询时间：{now}",
        ])

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"大盘行情查询失败: {e}")
        return f"大盘行情查询失败: {e}"

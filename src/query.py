#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行情查询模块 - 获取实时行情并格式化输出
供飞书机器人回复和定时推送共用
"""

import akshare as ak
import pandas as pd
from datetime import datetime
from monitor import SYMBOL, get_historical_data, logger


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


def query_realtime():
    """获取 600839 实时行情并格式化为文本"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == SYMBOL]
        if row.empty:
            return f"未找到股票代码 {SYMBOL}"

        r = row.iloc[0]

        price = float(r.get('最新价', 0))
        change = float(r.get('涨跌额', 0))
        pct = float(r.get('涨跌幅', 0))

        direction = "🔴" if pct > 0 else ("🟢" if pct < 0 else "⚪")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            f"{direction} 四川长虹 ({SYMBOL}) 实时行情",
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
        ]

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

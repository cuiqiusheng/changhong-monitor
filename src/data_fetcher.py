#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行情数据获取模块
实时行情：腾讯财经 API（云服务器兼容，无 TLS 指纹拦截）
历史 K 线：腾讯财经 API
"""

import re
import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def _parse_tencent_spot(text, symbol):
    """解析腾讯实时行情响应"""
    m = re.search(r'v_s[hz]\w+="([^"]+)"', text)
    if not m:
        return None

    parts = m.group(1).split("~")
    if len(parts) < 50 or parts[2] != symbol:
        return None

    def _f(idx):
        try:
            return float(parts[idx])
        except (IndexError, ValueError):
            return 0.0

    return {
        "名称": parts[1],
        "代码": parts[2],
        "最新价": _f(3),
        "昨收": _f(4),
        "今开": _f(5),
        "成交量": _f(6),
        "涨跌额": _f(31),
        "涨跌幅": _f(32),
        "最高": _f(33),
        "最低": _f(34),
        "成交额": _f(37) * 10000,
        "换手率": _f(38),
        "市盈率-动态": _f(39),
        "振幅": _f(43),
        "流通市值": _f(44) * 1e8,
        "总市值": _f(45) * 1e8,
        "市净率": _f(46),
        "量比": _f(49),
    }


def fetch_spot(symbol="600839"):
    """获取单只股票实时行情，返回 dict"""
    prefix = "sh" if symbol.startswith("6") else "sz"
    url = f"https://qt.gtimg.cn/q={prefix}{symbol}"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return _parse_tencent_spot(resp.text, symbol)
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return None


def fetch_hist(symbol="600839", start_date="20250101", end_date="20260309"):
    """获取历史日线数据（前复权），返回 DataFrame"""
    prefix = "sh" if symbol.startswith("6") else "sz"
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{prefix}{symbol},day,{_fmt_date(start_date)},{_fmt_date(end_date)},500,qfq",
    }
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        stock_key = f"qfq{prefix}{symbol}" if f"qfq{prefix}{symbol}" in data.get("data", {}) else f"{prefix}{symbol}"
        klines = data.get("data", {}).get(stock_key, {})

        day_data = klines.get("day") or klines.get("qfqday") or []
        if not day_data:
            return pd.DataFrame()

        records = []
        for row in day_data:
            if len(row) >= 6:
                records.append({
                    "日期": row[0],
                    "开盘": float(row[1]),
                    "收盘": float(row[2]),
                    "最高": float(row[3]),
                    "最低": float(row[4]),
                    "成交量": float(row[5]) if len(row) > 5 else 0,
                    "成交额": 0,
                    "振幅": 0,
                    "涨跌幅": 0,
                    "涨跌额": 0,
                    "换手率": 0,
                })

        df = pd.DataFrame(records)

        if not df.empty and len(df) > 1:
            df["涨跌额"] = df["收盘"] - df["收盘"].shift(1)
            df["涨跌幅"] = (df["涨跌额"] / df["收盘"].shift(1) * 100).round(2)

        return df
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        return pd.DataFrame()


def _fmt_date(d):
    """'20250101' -> '2025-01-01'"""
    if len(d) == 8 and "-" not in d:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return d

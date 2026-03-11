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

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://quote.eastmoney.com/",
}


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
        "外盘": _f(7),
        "内盘": _f(8),
        "买1价": _f(9),  "买1量": _f(10),
        "买2价": _f(11), "买2量": _f(12),
        "买3价": _f(13), "买3量": _f(14),
        "买4价": _f(15), "买4量": _f(16),
        "买5价": _f(17), "买5量": _f(18),
        "卖1价": _f(19), "卖1量": _f(20),
        "卖2价": _f(21), "卖2量": _f(22),
        "卖3价": _f(23), "卖3量": _f(24),
        "卖4价": _f(25), "卖4量": _f(26),
        "卖5价": _f(27), "卖5量": _f(28),
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


def search_stock(keyword):
    """通过腾讯智能搜索查找股票，返回 (代码, 名称) 或 None

    支持输入股票代码、名称、拼音首字母（如 "gzmt", "贵州茅台", "600519"）
    """
    url = f"https://smartbox.gtimg.cn/s3/?q={keyword}&t=gp&fr=web"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        m = re.search(r'v_hint="([^"]*)"', resp.text)
        if not m or not m.group(1):
            return None
        items = m.group(1).split("^")
        for item in items:
            parts = item.split("~")
            if len(parts) >= 3:
                market = parts[0]  # sh / sz
                code = parts[1]
                name = parts[2]
                if market in ("sh", "sz") and len(code) == 6:
                    return (code, name)
        return None
    except Exception as e:
        logger.error(f"股票搜索失败: {e}")
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


def fetch_indices(codes):
    """批量获取指数实时行情，codes 为带前缀的列表如 ['sh000001', 'sz399001']，返回 dict 列表"""
    if not codes:
        return []
    query = ",".join(codes)
    url = f"https://qt.gtimg.cn/q={query}"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return _parse_tencent_batch(resp.text)
    except Exception as e:
        logger.error(f"获取指数行情失败: {e}")
        return []


def _parse_tencent_batch(text):
    """解析腾讯批量行情响应，每段 v_xxx=\"...\" 解析为一个 dict"""
    results = []
    for m in re.finditer(r'v_(s[hz]\w+)="([^"]*)"', text):
        raw = m.group(2)
        if not raw:
            continue
        parts = raw.split("~")
        if len(parts) < 50:
            continue

        def _f(idx, _p=parts):
            try:
                return float(_p[idx])
            except (IndexError, ValueError):
                return 0.0

        results.append({
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
            "振幅": _f(43),
        })
    return results


def fetch_market_breadth():
    """获取上证/深证/创业板的涨跌家数（东方财富 API，失败静默降级）

    返回格式: {"000001": {"up": 2431, "down": 1892, "flat": 203}, ...}
    """
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        "fltt": 2,
        "secids": "1.000001,0.399001,0.399006",
        "fields": "f12,f104,f105,f106",
    }
    try:
        resp = requests.get(url, params=params, headers=_BROWSER_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        result = {}
        for item in data.get("data", {}).get("diff", []):
            code = item.get("f12", "")
            result[code] = {
                "up": int(item.get("f104", 0)),
                "down": int(item.get("f105", 0)),
                "flat": int(item.get("f106", 0)),
            }
        return result
    except Exception as e:
        logger.debug(f"获取涨跌家数失败（静默降级）: {e}")
        return {}


def _fmt_date(d):
    """'20250101' -> '2025-01-01'"""
    if len(d) == 8 and "-" not in d:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return d

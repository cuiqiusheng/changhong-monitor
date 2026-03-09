#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富 API 数据获取模块
使用 curl_cffi 模拟浏览器 TLS 指纹，绕过云服务器 IP 拦截
"""

from curl_cffi import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

_SESSION = requests.Session(impersonate="chrome110")

_SPOT_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23"

_SPOT_FIELD_MAP = {
    "f2": "最新价", "f3": "涨跌幅", "f4": "涨跌额",
    "f5": "成交量", "f6": "成交额", "f7": "振幅",
    "f8": "换手率", "f9": "市盈率-动态", "f10": "量比",
    "f12": "代码", "f14": "名称",
    "f15": "最高", "f16": "最低", "f17": "今开", "f18": "昨收",
    "f20": "总市值", "f21": "流通市值", "f23": "市净率",
}


def fetch_spot(symbol="600839"):
    """获取单只股票实时行情，返回 dict（列名与 akshare stock_zh_a_spot_em 兼容）"""
    market = 1 if symbol.startswith("6") else 0
    fs = "m:1+t:2,m:1+t:23" if market == 1 else "m:0+t:6,m:0+t:80,m:0+t:81+s:2048"

    resp = _SESSION.get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "5000", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": fs,
            "fields": _SPOT_FIELDS,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    diff = data.get("data", {}).get("diff", {})
    for item in diff.values():
        if str(item.get("f12")) == symbol:
            return {_SPOT_FIELD_MAP.get(k, k): v for k, v in item.items() if k in _SPOT_FIELD_MAP}

    return None


def fetch_spot_df(symbol="600839"):
    """获取单只股票实时行情，返回单行 DataFrame"""
    row = fetch_spot(symbol)
    if row is None:
        return pd.DataFrame()
    return pd.DataFrame([row])


def fetch_hist(symbol="600839", start_date="20250101", end_date="20260309"):
    """获取历史日线数据，返回 DataFrame（前复权）"""
    market = 1 if symbol.startswith("6") else 0
    secid = f"{market}.{symbol}"

    resp = _SESSION.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "beg": start_date,
            "end": end_date,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    klines = data.get("data", {}).get("klines")
    if not klines:
        return pd.DataFrame()

    records = []
    for line in klines:
        p = line.split(",")
        if len(p) >= 11:
            records.append({
                "日期": p[0], "开盘": float(p[1]), "收盘": float(p[2]),
                "最高": float(p[3]), "最低": float(p[4]),
                "成交量": float(p[5]), "成交额": float(p[6]),
                "振幅": float(p[7]), "涨跌幅": float(p[8]),
                "涨跌额": float(p[9]), "换手率": float(p[10]),
            })

    return pd.DataFrame(records)

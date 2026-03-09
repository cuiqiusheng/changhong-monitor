#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四川长虹监控模块 - 三因子策略版
三因子：价格因子 + 技术因子（RSI/MACD/成交量）+ 资金因子（主力资金流向）
"""

import os
import requests
import akshare as ak
import akshare.utils.request as _ak_req
import pandas as pd
from datetime import datetime, timedelta
import logging
import sys

# 东方财富 API 对云服务器做了 TLS 指纹检测，标准 requests 会被拒绝。
# 用 curl_cffi 模拟浏览器 TLS 指纹来绕过。
try:
    from curl_cffi import requests as _cffi_req

    def _cffi_request_with_retry(url, params=None, timeout=30, **kwargs):
        resp = _cffi_req.get(url, params=params, timeout=timeout, impersonate="chrome110")
        resp.raise_for_status()
        return resp

    _ak_req.request_with_retry = _cffi_request_with_retry
except ImportError:
    pass

# ==================== 配置 ====================
FEISHU_WEBHOOK = os.environ.get('FEISHU_WEBHOOK', '')

SYMBOL = "600839"

BASE_BUY_PRICE = 9.50
BASE_SELL_PRICE = 10.50

RSI_OVERSELL = 30
RSI_OVERBUY = 75
VOLUME_RATIO = 0.6

LAST_NOTIFY_FILE = os.environ.get('LAST_NOTIFY_FILE', '/app/data/last_notify.txt')
LOG_FILE = os.environ.get('LOG_FILE', '/app/logs/monitor.log')

handlers = [logging.StreamHandler(sys.stdout)]
_log_dir = os.path.dirname(LOG_FILE)
if _log_dir and os.path.isdir(_log_dir):
    handlers.append(logging.FileHandler(LOG_FILE))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers,
)
logger = logging.getLogger(__name__)

# ==================== 历史数据缓存 ====================
_hist_cache = {'data': None, 'updated_at': None}
HIST_CACHE_TTL = 1800


def is_trading_time():
    """判断当前是否为 A 股交易时段（工作日 9:30-11:30, 13:00-15:00）"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return (930 <= t <= 1130) or (1300 <= t <= 1500)


# ==================== 数据获取 ====================

def get_current_price():
    """获取实时价格"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == SYMBOL]
        if row.empty:
            logger.error(f"未找到股票代码 {SYMBOL}")
            return None
        return float(row['最新价'].values[0])
    except Exception as e:
        logger.error(f"获取价格失败: {e}")
        return None


_HIST_COLUMN_MAP = {
    '日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high',
    '最低': 'low', '成交量': 'volume', '成交额': 'amount',
    '振幅': 'amplitude', '涨跌幅': 'pct_change', '涨跌额': 'change', '换手率': 'turnover',
}


def get_historical_data(days=60):
    """获取历史日线数据（带 30 分钟缓存，避免频繁请求被限流）"""
    now = datetime.now()
    if (_hist_cache['data'] is not None
            and _hist_cache['updated_at']
            and (now - _hist_cache['updated_at']).total_seconds() < HIST_CACHE_TTL):
        return _hist_cache['data']

    try:
        end_date = now.strftime('%Y%m%d')
        start_date = (now - timedelta(days=days)).strftime('%Y%m%d')

        df = ak.stock_zh_a_hist(
            symbol=SYMBOL, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq",
        )
        if df is None or df.empty:
            return _hist_cache['data']

        df.rename(columns=_HIST_COLUMN_MAP, inplace=True)

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

        df = _calculate_indicators(df)

        _hist_cache['data'] = df
        _hist_cache['updated_at'] = now
        return df
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        return _hist_cache['data']


# ==================== 技术指标 ====================

def _calculate_indicators(df):
    """计算 RSI / MACD / 5日均量"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    df['volume_ma5'] = df['volume'].rolling(window=5).mean()
    return df


def _detect_divergence(df, lookback=20):
    """检测 MACD 顶背离 / 底背离"""
    if len(df) < lookback:
        return {'top': False, 'bottom': False}

    recent = df.iloc[-lookback:]

    # 底背离：价格创新低但 MACD 没有同步创新低
    bottom_divergence = False
    price_low_idx = recent['close'].idxmin()
    macd_low_idx = recent['macd'].idxmin()
    macd_low_value = recent['macd'].min()
    if price_low_idx > macd_low_idx:
        if recent.loc[price_low_idx, 'close'] < recent.loc[macd_low_idx, 'close']:
            if recent.loc[price_low_idx, 'macd'] > macd_low_value * 1.1:
                bottom_divergence = True

    # 顶背离：价格创新高但 MACD 没有同步创新高
    top_divergence = False
    price_high_idx = recent['close'].idxmax()
    macd_high_idx = recent['macd'].idxmax()
    macd_high_value = recent['macd'].max()
    if price_high_idx > macd_high_idx:
        if recent.loc[price_high_idx, 'close'] > recent.loc[macd_high_idx, 'close']:
            if recent.loc[price_high_idx, 'macd'] < macd_high_value * 0.9:
                top_divergence = True

    return {'top': top_divergence, 'bottom': bottom_divergence}


# ==================== 资金流向 ====================

def _get_fund_flow():
    """获取个股资金流向（失败时静默降级，不影响其他因子）"""
    try:
        df = ak.stock_individual_fund_flow(stock=SYMBOL, market="sh")
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.debug(f"获取资金流向失败: {e}")
    return None


# ==================== 综合评分 ====================

def _calculate_score(price, hist_data):
    """三因子综合评分：价格 + 技术 + 资金"""
    score = 0
    reasons = []

    if hist_data is None or len(hist_data) < 20:
        if price <= BASE_BUY_PRICE:
            score += 1
            reasons.append(f"价格≤{BASE_BUY_PRICE}")
        elif price >= BASE_SELL_PRICE:
            score -= 1
            reasons.append(f"价格≥{BASE_SELL_PRICE}")
        return score, reasons

    latest = hist_data.iloc[-1]

    # === 价格因子 ===
    if price <= BASE_BUY_PRICE:
        score += 1
        reasons.append(f"价格≤{BASE_BUY_PRICE}")
    elif price >= BASE_SELL_PRICE:
        score -= 1
        reasons.append(f"价格≥{BASE_SELL_PRICE}")

    # === 技术因子 ===
    rsi = latest.get('rsi')
    if rsi is not None and not pd.isna(rsi):
        if rsi < RSI_OVERSELL:
            score += 1
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi > RSI_OVERBUY:
            score -= 1
            reasons.append(f"RSI超买({rsi:.1f})")

    divergence = _detect_divergence(hist_data)
    if divergence['bottom']:
        score += 2
        reasons.append("MACD底背离")
    if divergence['top']:
        score -= 2
        reasons.append("MACD顶背离")

    volume = latest.get('volume')
    volume_ma5 = latest.get('volume_ma5')
    if (volume is not None and volume_ma5 is not None
            and not pd.isna(volume) and not pd.isna(volume_ma5) and volume_ma5 > 0):
        if volume < volume_ma5 * VOLUME_RATIO and price <= BASE_BUY_PRICE + 0.3:
            score += 1
            reasons.append("成交量萎缩")

    # === 资金因子 ===
    fund_flow = _get_fund_flow()
    if fund_flow is not None:
        try:
            main_col = next((c for c in fund_flow.columns if '主力净流入' in c), None)
            if main_col:
                main_flow = float(fund_flow[main_col].iloc[-1])
                if main_flow > 0 and price <= BASE_BUY_PRICE + 0.3:
                    score += 1
                    reasons.append("主力净流入")
                elif main_flow < 0 and price >= BASE_SELL_PRICE - 0.3:
                    score -= 1
                    reasons.append("主力净流出")
        except Exception as e:
            logger.debug(f"解析资金流向失败: {e}")

    return score, reasons


# ==================== 飞书推送 ====================

def send_feishu(content):
    """发送飞书消息"""
    if not FEISHU_WEBHOOK:
        logger.warning("飞书 Webhook 未配置")
        return False
    try:
        data = {"msg_type": "text", "content": {"text": content}}
        resp = requests.post(FEISHU_WEBHOOK, json=data, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
        return False


# ==================== 主监控 ====================

def check_and_notify():
    """主监控函数：综合三因子判断并推送"""
    price = get_current_price()
    if price is None:
        return

    hist_data = get_historical_data(days=60)
    score, reasons = _calculate_score(price, hist_data)

    action = None
    signal_type = ""
    if score >= 3:
        action = "强力买入"
        signal_type = "🔴🔴 强力买入信号"
    elif score == 2:
        action = "温和买入"
        signal_type = "🔴 买入信号"
    elif score <= -3:
        action = "强力卖出"
        signal_type = "🟢🟢 强力卖出信号"
    elif score == -2:
        action = "温和卖出"
        signal_type = "🟢 卖出信号"
    else:
        logger.debug(f"无信号，当前价格 {price:.2f}，得分 {score}")
        return

    last_price = 0
    last_action = ""
    if os.path.exists(LAST_NOTIFY_FILE):
        try:
            with open(LAST_NOTIFY_FILE, 'r') as f:
                raw = f.read().strip()
                if raw and '|' in raw:
                    last_price, last_action = raw.split('|')
                    last_price = float(last_price)
        except (ValueError, IOError) as e:
            logger.warning(f"读取上次推送状态失败: {e}")

    if action == last_action and abs(price - last_price) < 0.2:
        logger.debug("相同信号已推送过，跳过")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if '买入' in action:
        position_advice = '加仓至40%' if '强力' in action else '加仓至30%'
    else:
        position_advice = '减仓至10%' if '强力' in action else '减仓至20%'

    content = f"""{signal_type}

股票：四川长虹 ({SYMBOL})
当前价格：{price:.2f} 元
策略得分：{score}
触发因子：{', '.join(reasons)}
时间：{current_time}

建议操作：
- 机动仓：{position_advice}
- 底仓（70%）：继续持有"""

    pushed = send_feishu(content)

    if pushed:
        os.makedirs(os.path.dirname(LAST_NOTIFY_FILE), exist_ok=True)
        with open(LAST_NOTIFY_FILE, 'w') as f:
            f.write(f"{price}|{action}")
        logger.info(f"信号推送成功: {action} at {price:.2f} (得分:{score})")
    else:
        logger.error("推送失败")

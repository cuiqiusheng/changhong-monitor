#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票监控程序 - 四川长虹价格监控 + 飞书推送
"""

import os
import time
import logging
import requests
import akshare as ak
from datetime import datetime
import sys

FEISHU_WEBHOOK = os.environ.get('FEISHU_WEBHOOK', '')

SYMBOL = "600839"
BUY_PRICE = 9.50
SELL_PRICE = 10.50

LAST_NOTIFY_FILE = os.environ.get('LAST_NOTIFY_FILE', '/app/data/last_notify.txt')

LOG_FILE = os.environ.get('LOG_FILE', '/app/logs/monitor.log')

handlers = [logging.StreamHandler(sys.stdout)]
log_dir = os.path.dirname(LOG_FILE)
if log_dir and os.path.isdir(log_dir):
    handlers.append(logging.FileHandler(LOG_FILE))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers,
)
logger = logging.getLogger(__name__)


def is_trading_time():
    """判断当前是否为 A 股交易时段（工作日 9:30-11:30, 13:00-15:00）"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return (930 <= t <= 1130) or (1300 <= t <= 1500)


def get_current_price():
    """获取当前股票价格（akshare）"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == SYMBOL]
        if row.empty:
            logger.error(f"未找到股票代码 {SYMBOL}")
            return None
        price = float(row['最新价'].values[0])
        return price
    except Exception as e:
        logger.error(f"获取股票价格失败: {e}")
        return None


def send_feishu(content):
    """发送飞书消息"""
    if not FEISHU_WEBHOOK:
        logger.warning("飞书 Webhook 未配置，无法发送消息")
        return False
    try:
        data = {"msg_type": "text", "content": {"text": content}}
        resp = requests.post(FEISHU_WEBHOOK, json=data, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"发送飞书消息失败: {e}")
        return False


def check_and_notify():
    """检查价格并推送"""
    price = get_current_price()
    if price is None:
        return

    last_price = 0
    last_action = ""
    if os.path.exists(LAST_NOTIFY_FILE):
        try:
            with open(LAST_NOTIFY_FILE, 'r') as f:
                content = f.read().strip()
                if content and '|' in content:
                    last_price, last_action = content.split('|')
                    last_price = float(last_price)
        except (ValueError, IOError) as e:
            logger.warning(f"读取上次推送状态失败: {e}")

    action = None
    signal_type = ""
    if price <= BUY_PRICE:
        action = "买入"
        signal_type = "🔴 买入信号"
    elif price >= SELL_PRICE:
        action = "卖出"
        signal_type = "🟢 卖出信号"

    if action and (action != last_action or abs(price - last_price) > 0.2):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"""{signal_type}

股票：四川长虹 ({SYMBOL})
当前价格：{price:.2f} 元
触发条件：{'≤9.50' if action=='买入' else '≥10.50'}
时间：{current_time}

建议操作：{'考虑买入机动仓' if action=='买入' else '考虑卖出机动仓'}"""

        pushed = send_feishu(content)

        if pushed:
            os.makedirs(os.path.dirname(LAST_NOTIFY_FILE), exist_ok=True)
            with open(LAST_NOTIFY_FILE, 'w') as f:
                f.write(f"{price}|{action}")
            logger.info(f"信号推送成功: {action} at {price:.2f}")
    else:
        logger.debug(f"无新信号，当前价格 {price:.2f}")

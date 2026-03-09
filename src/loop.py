#!/usr/bin/env python3
"""
监控循环 - 容器入口
包含三因子信号监控 + 开盘/收盘定时行情推送
"""

import time
from datetime import datetime
from monitor import check_and_notify, is_trading_time, send_feishu, logger
from query import query_realtime

TRADING_INTERVAL = 60
NON_TRADING_INTERVAL = 300

_daily_push_done = {'open': None, 'close': None}


def _check_scheduled_push():
    """在交易日 9:35 和 15:05 自动推送行情摘要"""
    now = datetime.now()
    if now.weekday() >= 5:
        return

    today = now.strftime('%Y-%m-%d')
    t = now.hour * 100 + now.minute

    if 935 <= t <= 940 and _daily_push_done.get('open') != today:
        result = query_realtime()
        if send_feishu(f"📊 开盘行情推送\n\n{result}"):
            _daily_push_done['open'] = today
            logger.info("开盘行情推送成功")

    if 1505 <= t <= 1510 and _daily_push_done.get('close') != today:
        result = query_realtime()
        if send_feishu(f"📊 收盘行情推送\n\n{result}"):
            _daily_push_done['close'] = today
            logger.info("收盘行情推送成功")


if __name__ == "__main__":
    logger.info("四川长虹监控容器启动")
    while True:
        try:
            _check_scheduled_push()
            if is_trading_time():
                check_and_notify()
                time.sleep(TRADING_INTERVAL)
            else:
                logger.debug("非交易时段，跳过检查")
                time.sleep(NON_TRADING_INTERVAL)
        except KeyboardInterrupt:
            logger.info("监控容器停止")
            break
        except Exception as e:
            logger.error(f"监控循环异常: {e}")
            time.sleep(TRADING_INTERVAL)

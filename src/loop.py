#!/usr/bin/env python3
"""
监控循环 - 容器入口
"""

import time
from monitor import check_and_notify, is_trading_time, logger

TRADING_INTERVAL = 60
NON_TRADING_INTERVAL = 300

if __name__ == "__main__":
    logger.info("四川长虹监控容器启动")
    while True:
        try:
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

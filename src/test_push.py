#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送测试脚本 - 模拟四种信号场景发送飞书消息
本地使用: source venv/bin/activate && cd src && FEISHU_WEBHOOK="你的webhook" python test_push.py
容器使用: docker exec -it changhong-monitor python src/test_push.py
"""

import sys
import time
import logging
from datetime import datetime
from monitor import send_feishu, FEISHU_WEBHOOK, SYMBOL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCENARIOS = [
    {
        'action': '强力买入',
        'signal_type': '🔴🔴 强力买入信号',
        'price': 9.35,
        'score': 4,
        'reasons': ['价格≤9.50', 'RSI超卖(25.3)', 'MACD底背离', '成交量萎缩'],
        'position_advice': '加仓至40%',
    },
    {
        'action': '温和买入',
        'signal_type': '🔴 买入信号',
        'price': 9.48,
        'score': 2,
        'reasons': ['价格≤9.50', 'RSI超卖(28.7)'],
        'position_advice': '加仓至30%',
    },
    {
        'action': '温和卖出',
        'signal_type': '🟢 卖出信号',
        'price': 10.55,
        'score': -2,
        'reasons': ['价格≥10.50', 'RSI超买(76.2)'],
        'position_advice': '减仓至20%',
    },
    {
        'action': '强力卖出',
        'signal_type': '🟢🟢 强力卖出信号',
        'price': 10.82,
        'score': -4,
        'reasons': ['价格≥10.50', 'RSI超买(81.5)', 'MACD顶背离', '主力净流出'],
        'position_advice': '减仓至10%',
    },
]


def build_message(s):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""[测试] {s['signal_type']}

股票：四川长虹 ({SYMBOL})
当前价格：{s['price']:.2f} 元
策略得分：{s['score']}
触发因子：{', '.join(s['reasons'])}
时间：{current_time}

建议操作：
- 机动仓：{s['position_advice']}
- 底仓（70%）：继续持有"""


def main():
    if not FEISHU_WEBHOOK:
        logger.error("❌ 飞书 Webhook 未配置，请设置 FEISHU_WEBHOOK 环境变量")
        sys.exit(1)

    logger.info(f"即将发送 {len(SCENARIOS)} 条测试消息到飞书...")

    success = 0
    for i, s in enumerate(SCENARIOS, 1):
        msg = build_message(s)
        logger.info(f"[{i}/{len(SCENARIOS)}] 发送: {s['action']} (得分 {s['score']})")
        if send_feishu(msg):
            logger.info(f"  ✅ {s['action']} 推送成功")
            success += 1
        else:
            logger.error(f"  ❌ {s['action']} 推送失败")
        if i < len(SCENARIOS):
            time.sleep(1)

    logger.info(f"测试完成: {success}/{len(SCENARIOS)} 条发送成功，请检查飞书是否收到消息")
    if success < len(SCENARIOS):
        sys.exit(1)


if __name__ == "__main__":
    main()

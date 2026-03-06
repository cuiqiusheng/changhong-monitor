#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送测试脚本 - 用于验证飞书消息能否正常到达
使用方法: docker exec -it changhong-monitor python src/test_push.py
"""

import sys
import logging
from monitor import send_feishu, FEISHU_WEBHOOK

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_feishu():
    """测试飞书推送"""
    if not FEISHU_WEBHOOK:
        logger.error("❌ 飞书 Webhook 未配置，请在 .env 文件中设置 FEISHU_WEBHOOK")
        return False

    test_message = "🧪 这是一条来自长虹监控容器的测试消息\n\n如果收到这条消息，说明推送配置正确！"

    logger.info("正在测试飞书推送...")
    if send_feishu(test_message):
        logger.info("✅ 飞书推送成功")
        return True
    else:
        logger.error("❌ 飞书推送失败")
        return False


if __name__ == "__main__":
    logger.info("开始测试推送功能...")
    if test_feishu():
        logger.info("🎉 测试完成，请检查手机是否收到消息")
    else:
        logger.error("测试失败，请检查配置")
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人 HTTP 服务
接收飞书事件回调，匹配关键词后回复实时行情数据
"""

import os
import re
import json
import logging
import sys
import threading

from flask import Flask, request, jsonify
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from query import query_realtime, query_market

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
FEISHU_VERIFY_TOKEN = os.environ.get('FEISHU_VERIFY_TOKEN', '')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

client = lark.Client.builder() \
    .app_id(FEISHU_APP_ID) \
    .app_secret(FEISHU_APP_SECRET) \
    .build()

STOCK_KEYWORDS = ['查询', '长虹', '股票']
MARKET_KEYWORDS = ['大盘', '指数']
ALL_KEYWORDS = STOCK_KEYWORDS + MARKET_KEYWORDS + ['行情']

_processed_events = set()
_MAX_EVENTS = 500


def _send_reply(chat_id, text):
    """通过飞书 Open API 向会话发送消息"""
    try:
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ) \
            .build()

        resp = client.im.v1.message.create(req)
        if not resp.success():
            logger.error(f"回复失败: code={resp.code} msg={resp.msg}")
    except Exception as e:
        logger.error(f"发送回复异常: {e}")


def _handle_message(event_data):
    """处理消息事件（在后台线程运行，避免阻塞回调响应）"""
    message = event_data.get('message', {})
    msg_type = message.get('message_type', '')
    chat_id = message.get('chat_id', '')

    if msg_type != 'text' or not chat_id:
        return

    try:
        content = json.loads(message.get('content', '{}'))
    except json.JSONDecodeError:
        return

    text = content.get('text', '').strip()
    text = re.sub(r'@_user_\d+\s*', '', text).strip()

    if not any(kw in text for kw in ALL_KEYWORDS):
        return

    logger.info(f"收到查询请求: '{text}' from chat {chat_id}")

    if any(kw in text for kw in MARKET_KEYWORDS):
        result = query_market()
    else:
        result = query_realtime()
    _send_reply(chat_id, result)


@app.route('/callback', methods=['POST'])
def callback():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"code": 400}), 400

    if 'challenge' in data:
        return jsonify({"challenge": data['challenge']})

    header = data.get('header', {})

    token = header.get('token', '')
    if FEISHU_VERIFY_TOKEN and token != FEISHU_VERIFY_TOKEN:
        logger.warning("验证 token 不匹配，拒绝请求")
        return jsonify({"code": 403}), 403

    event_id = header.get('event_id', '')
    if event_id in _processed_events:
        return jsonify({"code": 0})
    _processed_events.add(event_id)
    if len(_processed_events) > _MAX_EVENTS:
        _processed_events.clear()

    event_type = header.get('event_type', '')
    if event_type == 'im.message.receive_v1':
        event = data.get('event', {})
        threading.Thread(target=_handle_message, args=(event,), daemon=True).start()

    return jsonify({"code": 0})


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        logger.error("请配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
        sys.exit(1)
    logger.info("飞书机器人服务启动，监听端口 9000")
    app.run(host='0.0.0.0', port=9000)

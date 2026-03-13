# stock-monitor · A 股智能监控系统

基于三因子策略的 A 股监控系统，当前默认监控标的为四川长虹（600839），通过飞书进行信号推送和实时行情交互。

## 功能概览

### 三因子策略监控

综合三类因子打分，触发买入/卖出信号时自动推送飞书通知：

- **价格因子**：突破预设买卖价位
- **技术因子**：RSI 超买超卖、MACD 背离、成交量异动
- **资金因子**：主力资金净流入/流出

### 波动提醒

实时监测涨跌幅，突破 ±3%、±5%、±7%、±9% 阈值时推送预警，每档每天单向仅触发一次。

### 定时行情推送

交易日 5 个关键时段自动推送**大盘行情 + 个股行情**（分两条消息）：

| 时间 | 内容 |
|------|------|
| 9:35 | 开盘速报 |
| 10:30 | 早盘中段 |
| 11:35 | 午盘收盘 |
| 13:05 | 午后开盘 |
| 15:05 | 收盘总结 |

大盘行情包含：
- **详细展示**：上证指数、深证成指、创业板指（成交额 + 涨跌家数）
- **宽基指数**：沪深300、上证50、中证500、中证1000、中证2000

### 飞书机器人交互

在飞书群中 @机器人 发送消息，即时回复对应行情数据：

| 输入方式 | 示例 | 功能 |
|---------|------|------|
| 6位股票代码 | `600519` | 查询对应股票行情 |
| 关键词 + 股票名称 | `查询 贵州茅台` | 搜索并查询指定股票 |
| 关键词 + 拼音首字母 | `查询 gzmt` | 按拼音缩写搜索股票 |
| 直接输入股票名称 | `贵州茅台` | 自动识别并查询 |
| 默认关键词 | `查询` `长虹` `股票` `行情` | 查询默认监控股票（四川长虹） |
| 大盘关键词 | `大盘` `指数` | 大盘行情概览（主要指数 + 涨跌家数） |

## 项目结构

```
├── src/
│   ├── loop.py          # 主循环入口（监控 + 定时推送 + 波动提醒）
│   ├── monitor.py       # 三因子策略 + 波动检测 + 飞书推送
│   ├── data_fetcher.py  # 行情数据获取（腾讯财经 + 东方财富 API）
│   ├── query.py         # 个股/大盘行情查询与格式化
│   ├── bot.py           # 飞书机器人 HTTP 服务（Flask）
│   └── test_push.py     # 推送测试脚本
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                 # 环境变量配置（不入库）
```

## 部署

### 前置条件

- Docker & Docker Compose
- 飞书自定义机器人 Webhook（用于推送通知）
- 飞书应用 App ID / App Secret（用于双向交互，可选）

### 1. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

```env
# 飞书 Webhook（必填，用于信号推送和定时行情）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/your-token

# 飞书应用配置（可选，用于双向交互机器人）
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_VERIFY_TOKEN=your_verify_token
```

### 2. 启动服务

```bash
docker compose up -d --build
```

服务说明：

| 服务 | 容器名 | 功能 |
|------|--------|------|
| stock-monitor | stock-monitor | 策略监控 + 定时推送（大盘+个股） + 波动提醒 |
| stock-bot | stock-bot | 飞书机器人交互服务（端口 9000） |

### 3. 查看日志

```bash
# 监控服务日志
docker logs -f stock-monitor

# 机器人服务日志
docker logs -f stock-bot
```

## 测试

```bash
# 测试所有推送（三因子信号 + 波动提醒 + 大盘行情）
docker exec -it stock-monitor python src/test_push.py

# 仅测试三因子信号推送
docker exec -it stock-monitor python src/test_push.py signal

# 仅测试波动提醒推送
docker exec -it stock-monitor python src/test_push.py volatility

# 仅测试大盘行情推送（拉取实时数据）
docker exec -it stock-monitor python src/test_push.py market
```

本地测试（需先激活虚拟环境）：

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd src && FEISHU_WEBHOOK="你的webhook" python test_push.py
```

## 策略参数

在 `src/monitor.py` 中调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SYMBOL` | 600839 | 监控股票代码（默认四川长虹） |
| `BASE_BUY_PRICE` | 9.50 | 买入价格阈值 |
| `BASE_SELL_PRICE` | 10.50 | 卖出价格阈值 |
| `RSI_OVERSELL` | 30 | RSI 超卖线 |
| `RSI_OVERBUY` | 75 | RSI 超买线 |
| `VOLUME_RATIO` | 0.6 | 缩量判定（相对 5 日均量） |
| `_VOLATILITY_THRESHOLDS` | [3, 5, 7, 9] | 波动提醒阈值（%） |

## 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 个股实时行情 | 腾讯财经 API | 云服务器友好，无 TLS 指纹拦截 |
| 历史 K 线 | 腾讯财经 API | 前复权日线数据 |
| 指数行情 | 腾讯财经 API | 批量查询，一次请求获取所有指数 |
| 涨跌家数 | 东方财富 API | 模拟浏览器请求，失败时静默降级 |
| 资金流向 | akshare | 失败时静默降级，不影响其他因子 |

# 使用 Python 3.11 轻量版作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置时区（确保时间正确）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装依赖（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/

# 创建日志目录
RUN mkdir -p /app/logs

# 设置容器启动命令
CMD ["python", "-u", "src/loop.py"]
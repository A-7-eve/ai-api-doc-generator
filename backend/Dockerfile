# 后端镜像：FastAPI + uvicorn（Python 3.12）
# 构建上下文为 backend/ 目录（见 docker-compose.yml 的 build.context）

FROM python:3.12-slim

# 时区（日志时间戳可读）
ENV TZ=Asia/Shanghai

WORKDIR /app

# 先复制依赖清单再安装，充分利用镜像层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码（.dockerignore 已排除 tests / .env / __pycache__）
COPY . .

# 容器内固定 8000；宿主端口由 compose 映射
EXPOSE 8000

# 健康检查：/health 端点
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["python", "main.py"]

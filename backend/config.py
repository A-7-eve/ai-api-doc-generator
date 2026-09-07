"""配置文件：大模型 API、MySQL 数据库、服务端口等设置"""

import os

# ========== 大模型 API 配置 ==========
# 支持 DeepSeek / 豆包 等 OpenAI 兼容接口
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # 使用前请填入你的 API Key
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TEMPERATURE = 0.3
LLM_TIMEOUT = 30  # 秒

# ========== AI 增强并发控制 ==========
MAX_CONCURRENT_AI = 5  # 最多同时调用 5 个大模型请求

# ========== 服务配置 ==========
HOST = "0.0.0.0"
PORT = 8000

# ========== MySQL 数据库配置（环境变量可覆盖） ==========
DB_HOST = os.getenv("APIDOC_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("APIDOC_DB_PORT", "3306"))
DB_USER = os.getenv("APIDOC_DB_USER", "root")
DB_PASSWORD = os.getenv("APIDOC_DB_PASSWORD", "123456")
DB_NAME = os.getenv("APIDOC_DB_NAME", "apidoc")

# 测试专用库名（pytest 隔离用，与真实数据分离）
DB_NAME_TEST = DB_NAME + "_test"

# ========== 被解析项目默认路径 ==========
SAMPLE_PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample-project",
    "spring-petclinic",
)

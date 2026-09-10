"""配置文件：大模型 API、MySQL 数据库、服务端口等设置

Key 读取优先级（v2.4 安全方案，Key 不进仓库）：
1. 环境变量 LLM_API_KEY
2. backend/.env 文件中的 LLM_API_KEY（.env 已被 .gitignore 排除）
3. 均为空 → AI 增强自动降级为纯解析模式
"""

import os


def _load_dotenv(path: str) -> None:
    """极简 .env 加载器（避免额外依赖）

    只支持 KEY=VALUE 单行格式，# 开头为注释
    """
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            # 环境变量优先，.env 不覆盖已存在的
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# ========== 大模型 API 配置 ==========
# 支持 DeepSeek / 豆包 等 OpenAI 兼容接口
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # 从环境变量或 backend/.env 读取
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

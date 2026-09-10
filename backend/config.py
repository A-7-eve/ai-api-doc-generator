"""配置文件：大模型 API、MySQL 数据库、服务端口等设置

大模型双供应商（v2.5）：LLM_PROVIDER 预设切换 deepseek / teleai（中电信星辰）
Key 读取优先级（v2.4 安全方案，Key 不进仓库）：
1. 环境变量 / backend/.env 中的 LLM_API_KEY（通用）
2. 供应商专属变量（如 teleai 的 TELEAI_API_KEY）
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


# ========== 大模型 API 配置（v2.5 双供应商） ==========
# 供应商预设：LLM_PROVIDER=deepseek | teleai | custom
#   deepseek（默认）  → DeepSeek 官方 API
#   teleai            → 中电信星辰大模型（天翼AI开放平台，OpenAI 兼容协议）
#   custom            → 任意 OpenAI 兼容接口，URL/模型由 LLM_API_URL / LLM_MODEL 指定
# 选择预设后，仅需在 backend/.env 配置对应 Key（LLM_API_KEY 或 TELEAI_API_KEY）即可切换。
LLM_PROVIDERS = {
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "key_env": "LLM_API_KEY",       # Key 读取的环境变量
    },
    "teleai": {
        # 中电信星辰大模型（天翼AI开放平台 https://www.teleai.com.cn/）
        # API 终端地址参考天翼云文档（OpenAI 协议）：
        #   https://ai.ctaigw.cn/v1/chat/completions
        # 模型名以平台控制台实际开通的为准（如 TeleChat 系列）
        "url": "https://ai.ctaigw.cn/v1/chat/completions",
        "model": "TeleChat",
        "key_env": "TELEAI_API_KEY",    # 星辰平台申请的 API Key
    },
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

_preset = LLM_PROVIDERS.get(LLM_PROVIDER)

# URL / 模型：环境变量显式指定 > 供应商预设 > deepseek 默认值
if _preset is None:
    # 未知预设名视为 custom，保持显式配置优先
    LLM_PROVIDER = "custom"
    _preset = LLM_PROVIDERS["deepseek"]
    _default_url, _default_model = "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"
else:
    _default_url, _default_model = _preset["url"], _preset["model"]

LLM_API_URL = os.getenv("LLM_API_URL", _default_url)
LLM_MODEL = os.getenv("LLM_MODEL", _default_model)

# Key 读取（每个供应商只读自己的 Key，避免拿 A 家 Key 调 B 家 API）：
#   deepseek → LLM_API_KEY；teleai → TELEAI_API_KEY；custom → LLM_API_KEY
# 均从环境变量或 backend/.env 读取；为空 → AI 增强自动降级为纯解析模式
LLM_API_KEY = os.getenv(_preset["key_env"], "")
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
# Docker 部署时可用环境变量 APIDOC_SAMPLE_PATH 覆盖（compose 已注入 /app/sample-project）
_default_sample = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample-project",
    "spring-petclinic",
)
SAMPLE_PROJECT_PATH = os.getenv("APIDOC_SAMPLE_PATH", _default_sample)

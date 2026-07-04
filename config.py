"""
配置文件 - MiniSelfAgent 的全局配置
"""
import os
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ============================================================
# LLM 配置
# ============================================================
# 支持 OpenAI 兼容接口（如 OpenAI、DeepSeek、Moonshot 等）
LLM_API_KEY = os.environ.get("LLM_API_KEY", "your-api-key-here")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2048

# ============================================================
# Agent 配置
# ============================================================
MAX_LOOP_ITERATIONS = 10          # 单次用户输入最大循环轮次，防止死循环
CONTEXT_MAX_MESSAGES = 20         # context 中保留的最大消息数
CONTEXT_COMPRESS_THRESHOLD = 15   # 超过此条数触发压缩
CONTEXT_SUMMARY_MAX_TOKENS = 512  # 压缩摘要的最大 token 数

# ============================================================
# Session 配置
# ============================================================
SESSION_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")
SESSION_EXPIRY_SECONDS = 3600 * 24  # Session 24 小时过期

# ============================================================
# 天气 API 配置 (wttr.in - 免费，无需 API Key)
# ============================================================
WEATHER_API_URL = "https://wttr.in"
WEATHER_API_TIMEOUT = 10  # 秒
WEATHER_DEFAULT_CITY = "Beijing"

# ============================================================
# 日志配置
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), "data", "logs")
LOG_LEVEL = "INFO"

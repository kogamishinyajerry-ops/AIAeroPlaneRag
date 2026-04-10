"""
Core configuration module
集中管理所有配置常量和环境变量
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from src.settings import (
    APP_MODE,
    APP_VERSION,
    CATALOG_DIR,
    CHROMA_DB_DIR,
    DOCUMENT_VERSION,
    EMBEDDING_VERSION,
    GRAPH_VERSION,
    PROMPT_VERSION,
    PROCESSED_DATA_DIR,
    SOURCE_CATALOG_PATH,
    SOURCE_CATALOG_VERSION,
)

load_dotenv()


# === 应用配置 ===
ENABLE_LLMS = os.getenv("ENABLE_LLM", "true").lower() == "true"


# === 路径配置 ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
UI_DIR = PROJECT_ROOT / "ui"


# === API配置 ===
API_HOST = "0.0.0.0"
API_PORT = 8888


# === Embedding配置 ===
EMBEDDING_CONFIG = {
    "openai": {
        "key_env": "EMBEDDING_API_KEY",
        "model": "text-embedding-3-small",
    },
    "jina": {
        "key_env": "JINA_API_KEY",
        "model": "jina-embeddings-v3",
    },
    "ollama": {
        "key_env": "OLLAMA_API_KEY",
        "model": "nomic-embed-text",
        "base_url": "http://localhost:11434",
    },
    "minimax": {
        "key_env": "MINIMAX_API_KEY",
        "model": "embo-01",
        "base_url": "https://api.minimax.chat/v1",
    },
}


# === LLM配置 ===
LLM_CONFIG = {
    "zhipu": {
        "key_env": "ZHIPU_API_KEY",
        "model": "glm-4-flash",
    },
    "minimax": {
        "key_env": "MINIMAX_API_KEY",
        "model": "abab6.5s-chat",
        "base_url": "https://api.minimax.chat/v1",
    },
}


# === Neo4j配置 ===
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


# === 缓存配置 ===
CACHE_CONFIG = {
    "max_indexed_cache": 1000,
    "max_query_cache": 500,
    "cache_evict_ratio": 0.25,
}


# === CORS配置 ===
CORS_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
]


# === API Key认证配置 ===
API_KEYS = set()
if os.getenv("API_KEY"):
    API_KEYS.add(os.getenv("API_KEY"))

# === JWT认证配置 ===
import secrets
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))  # 默认60分钟

# === 速率限制配置 ===
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # 默认60请求/分钟
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))  # 滑动窗口60秒
# 分布式速率限制：redis 或 memory（默认 memory，Redis 仅在 RATE_LIMIT_STORAGE=redis 时使用）
RATE_LIMIT_STORAGE = os.getenv("RATE_LIMIT_STORAGE", "memory")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

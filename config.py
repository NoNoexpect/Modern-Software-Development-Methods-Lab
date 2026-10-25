"""全局配置：集中管理环境变量、路径与运行参数。

所有模块（智能体与 MCP Server）共用本文件，保证配置口径一致。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
BASE_DIR: Path = Path(__file__).resolve().parent

# 加载 .env（不覆盖已存在的系统环境变量）
load_dotenv(BASE_DIR / ".env")

# ---------- 大模型：DeepSeek（OpenAI 兼容接口） ----------
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

# ---------- 智能体运行参数 ----------
# 单轮对话内最多允许的"模型思考 + 工具调用"轮数，防止死循环
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "8"))
# 单次工具返回给模型的最大字符数，避免撑爆上下文
MAX_TOOL_CHARS: int = int(os.getenv("MAX_TOOL_CHARS", "8000"))

# ---------- 本地资料目录（智能体的文件访问沙箱） ----------
_workspace_env = os.getenv("WORKSPACE_DIR", "").strip()
WORKSPACE_DIR: Path = Path(_workspace_env).resolve() if _workspace_env else (BASE_DIR / "workspace")
NOTES_DIR: Path = WORKSPACE_DIR / "notes"

# ---------- MCP Server 启动方式 ----------
# MCP Server 以子进程 stdio 方式启动，模块名用于 `python -m` 调用
MCP_SERVER_MODULE: str = "mcp_server.server"

# ---------- MySQL（论文入库技能的数据落点） ----------
MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1").strip()
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "root").strip()
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "research_copilot").strip()
# 连接超时（秒），MySQL 不可达时快速失败并给出可读提示
MYSQL_TIMEOUT: int = int(os.getenv("MYSQL_TIMEOUT", "5"))

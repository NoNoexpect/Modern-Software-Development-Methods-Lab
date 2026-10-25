"""DeepSeek 大模型客户端封装（OpenAI 兼容接口）。"""

from __future__ import annotations

from openai import AsyncOpenAI

import config


def build_client() -> AsyncOpenAI:
    """构建异步 DeepSeek 客户端；未配置 API Key 时给出明确提示。"""
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在项目根目录的 .env 中填写。")
    return AsyncOpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )

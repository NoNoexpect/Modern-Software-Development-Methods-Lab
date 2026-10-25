"""工具层公共能力：工作区路径校验与文本截断。

所有本地文件类技能都必须经过 resolve_in_workspace 校验，
防止模型生成 `../` 形式的路径越界访问工作区之外的文件。
"""

from __future__ import annotations

from pathlib import Path

import config
from mcp.server.mcpserver.exceptions import ToolError

# 允许访问的根目录，所有本地文件操作都必须落在其内部
WORKSPACE_ROOT: Path = config.WORKSPACE_DIR


def resolve_in_workspace(raw_path: str) -> Path:
    """把相对路径解析为工作区内的绝对路径，越界则抛出 ToolError。

    抛出协议原生的 ToolError，客户端会收到可读的错误说明，
    而不是被当作服务端崩溃。

    Args:
        raw_path: 用户或模型给出的路径，可以是相对工作区或绝对路径。

    Returns:
        解析并校验后的绝对路径。
    """
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    resolved = candidate.resolve()
    if resolved != WORKSPACE_ROOT and WORKSPACE_ROOT not in resolved.parents:
        raise ToolError(f"路径越界：{raw_path} 不在工作区 {WORKSPACE_ROOT} 内")
    return resolved


def truncate(text: str, max_chars: int) -> str:
    """按字符数截断长文本，并标注被截断的提示。"""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...[内容过长已截断，原文共 {len(text)} 字符]"

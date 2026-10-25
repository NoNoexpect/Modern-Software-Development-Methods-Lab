"""笔记类技能：把整理结果持久化为工作区内的 Markdown 笔记。"""

from __future__ import annotations

import re
from datetime import datetime

import config
from mcp.server.mcpserver import MCPServer

from mcp_server.tools.common import resolve_in_workspace

# 文件名中不允许出现的字符
ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


def save_note(title: str, content: str, filename: str = "") -> str:
    """把整理好的内容保存为工作区 notes/ 目录下的 Markdown 笔记。

    Args:
        title: 笔记标题，会写入正文首行并作为默认文件名。
        content: 笔记正文，支持 Markdown 语法。
        filename: 可选的自定义文件名（不含扩展名），留空则由标题生成。
    """
    stem = _sanitize(filename or title)
    if not stem:
        stem = "note"
    target = resolve_in_workspace(f"notes/{stem}.md")
    target.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    heading = f"# {title.strip()}"
    stripped = content.strip()
    # 若正文首行已是同名标题，则不再重复插入
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if first_line == heading:
        body = f"{stripped}\n\n> 生成时间：{timestamp}\n"
    else:
        body = f"{heading}\n\n> 生成时间：{timestamp}\n\n{stripped}\n"
    target.write_text(body, encoding="utf-8")
    return f"笔记已保存：{target.relative_to(config.WORKSPACE_DIR)}（{len(body)} 字符）"


def register(mcp: MCPServer) -> None:
    """把本模块的技能注册到 MCP 服务。"""
    mcp.tool()(save_note)


def _sanitize(name: str) -> str:
    """清理文件名中的非法字符，并限制长度。"""
    cleaned = ILLEGAL_FILENAME_CHARS.sub("_", name.strip())
    return cleaned[:60].strip("_")

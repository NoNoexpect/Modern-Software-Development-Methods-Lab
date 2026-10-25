"""文件类技能：浏览工作区资料、解析 PDF / Word / 文本 / CSV / JSON。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import config
from mcp.server.mcpserver import MCPServer

from mcp_server.tools.common import resolve_in_workspace, truncate

# 支持解析的文件类型
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".csv", ".json"}


def list_local_files(subdir: str = "", pattern: str = "*") -> str:
    """列出工作区内的资料文件，用于先找到再读取。

    Args:
        subdir: 相对工作区的子目录，留空表示工作区根目录。
        pattern: 文件通配符，例如 "*.pdf" 只列出 PDF 文件。
    """
    directory = resolve_in_workspace(subdir) if subdir else config.WORKSPACE_DIR
    if not directory.exists():
        return f"目录不存在：{subdir or '.'}"
    if not directory.is_dir():
        return f"不是目录：{subdir}"
    files = sorted(p for p in directory.glob(pattern) if p.is_file())
    if not files:
        return f"未找到匹配 {pattern} 的文件（目录：{subdir or '.'}）。"
    lines = [f"工作区根目录：{config.WORKSPACE_DIR}", f"共找到 {len(files)} 个文件："]
    lines.extend(
        f"- {p.relative_to(config.WORKSPACE_DIR)}  ({p.stat().st_size / 1024:.1f} KB)"
        for p in files
    )
    return "\n".join(lines)


def read_document(path: str, max_chars: int = config.MAX_TOOL_CHARS) -> str:
    """读取并解析工作区内的资料文件正文。

    Args:
        path: 相对工作区的文件路径，例如 "paper.pdf" 或 "data/scores.csv"。
        max_chars: 返回内容的最大字符数，超出部分会被截断。
    """
    file_path = resolve_in_workspace(path)
    if not file_path.is_file():
        return f"文件不存在：{path}"

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(file_path)
    elif suffix == ".docx":
        text = _read_docx(file_path)
    elif suffix == ".csv":
        text = _read_csv_preview(file_path)
    elif suffix == ".json":
        text = _read_json(file_path)
    elif suffix in {".txt", ".md"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    else:
        return f"不支持的文件类型：{suffix}，仅支持 {sorted(SUPPORTED_SUFFIXES)}"

    return truncate(text.strip(), max_chars)


def register(mcp: MCPServer) -> None:
    """把本模块的技能注册到 MCP 服务。"""
    mcp.tool()(list_local_files)
    mcp.tool()(read_document)


# ---------- 以下为内部解析实现 ----------


def _read_pdf(file_path: Path) -> str:
    """逐页提取 PDF 文本。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "缺少依赖 pypdf，请先执行：pip install pypdf"
    reader = PdfReader(str(file_path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    body = "\n\n".join(f"[第 {i + 1} 页]\n{text}" for i, text in enumerate(pages))
    return f"[PDF 共 {len(pages)} 页]\n{body}"


def _read_docx(file_path: Path) -> str:
    """提取 Word 文档的段落文本。"""
    try:
        import docx
    except ImportError:
        return "缺少依赖 python-docx，请先执行：pip install python-docx"
    document = docx.Document(str(file_path))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return f"[Word 共 {len(paragraphs)} 段]\n" + "\n".join(paragraphs)


def _read_csv_preview(file_path: Path, max_rows: int = 50) -> str:
    """预览 CSV 前若干行，避免一次性灌入超大表格。"""
    with file_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return "CSV 文件为空。"
    preview = rows[:max_rows]
    body = "\n".join(",".join(cell for cell in row) for row in preview)
    return f"[CSV 共 {len(rows)} 行，以下为前 {len(preview)} 行]\n{body}"


def _read_json(file_path: Path) -> str:
    """读取 JSON 并格式化为缩进文本，便于模型理解结构。"""
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return raw

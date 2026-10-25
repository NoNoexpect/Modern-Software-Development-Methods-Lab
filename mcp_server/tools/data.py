"""数据类技能：对工作区内的 CSV 做列级统计摘要。

不依赖 pandas，直接用标准库实现，便于在任何环境下运行。
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from mcp_server.tools.common import resolve_in_workspace

# 判定为数值列的最低有效值比例
NUMERIC_RATIO_THRESHOLD = 0.8
# 枚举列最多展示的取值个数
MAX_DISTINCT_VALUES = 5


def analyze_csv(path: str) -> str:
    """对工作区内的 CSV 做列级统计，返回可读的统计摘要。

    Args:
        path: 相对工作区的 CSV 文件路径，例如 "data/scores.csv"。
    """
    file_path = resolve_in_workspace(path)
    if not file_path.is_file():
        return f"文件不存在：{path}"

    with file_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        return "CSV 至少需要表头加一行数据才能统计。"

    header, *data_rows = rows
    columns = _transpose(header, data_rows)
    if not columns:
        return "CSV 中未解析出有效列。"

    lines = [f"文件：{path}", f"数据行数：{len(data_rows)}", f"列数：{len(header)}", "", "各列统计："]
    for name, values in columns.items():
        lines.append(f"- 列「{name}」：{_summarize_column(values)}")
    return "\n".join(lines)


def register(mcp: MCPServer) -> None:
    """把本模块的技能注册到 MCP 服务。"""
    mcp.tool()(analyze_csv)


def _transpose(header: list[str], data_rows: list[list[str]]) -> dict[str, list[str]]:
    """按列名聚合各行的取值，行长度不足时补空串。"""
    columns: dict[str, list[str]] = {}
    for index, name in enumerate(header):
        label = name.strip() or f"第{index + 1}列"
        columns[label] = [
            (row[index].strip() if index < len(row) else "") for row in data_rows
        ]
    return columns


def _summarize_column(values: list[str]) -> str:
    """根据取值特征输出数值统计或类别枚举。"""
    non_empty = [value for value in values if value != ""]
    missing = len(values) - len(non_empty)
    if not non_empty:
        return f"全部为空（缺失 {missing} 项）"

    numbers = _to_floats(non_empty)
    if numbers is not None and len(numbers) >= len(non_empty) * NUMERIC_RATIO_THRESHOLD:
        return (
            f"数值型，有效 {len(numbers)} 项（缺失 {missing}），"
            f"最小 {min(numbers):g}，最大 {max(numbers):g}，"
            f"均值 {statistics.fmean(numbers):.4g}，"
            f"中位数 {statistics.median(numbers):g}"
        )

    distinct = sorted(set(non_empty))
    preview = "、".join(distinct[:MAX_DISTINCT_VALUES])
    suffix = " 等" if len(distinct) > MAX_DISTINCT_VALUES else ""
    return f"类别型，{len(distinct)} 个不同取值（缺失 {missing}）：{preview}{suffix}"


def _to_floats(values: list[str]) -> list[float] | None:
    """尝试把全部取值转为浮点数，失败返回 None。"""
    numbers: list[float] = []
    for value in values:
        try:
            numbers.append(float(value.replace(",", "")))
        except ValueError:
            return None
    return numbers

"""文本分块。

将长文本切分为带重叠(overlap)的片段,供向量化与检索使用。
默认按字符数切分并尽量在句子边界对齐,确定性、无外部依赖。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 默认分块参数(字符为单位)
DEFAULT_CHUNK_SIZE = 400
DEFAULT_OVERLAP = 80
# 句子结束标点(中英文),用于尽量在边界处断开
_SENTENCE_END = re.compile(r"(?<=[。!?!?.;;\n])")


@dataclass(frozen=True)
class Chunk:
    """单个文本片段。

    属性:
        index: 片段在原文中的序号(从 0 开始)。
        text: 片段文本。
        start: 在原文中的起始字符偏移。
        end: 在原文中的结束字符偏移(不含)。
    """

    index: int
    text: str
    start: int
    end: int


def _normalize(text: str) -> str:
    """规整文本:去除首尾空白。"""
    return text.strip()


def _find_break(text: str, start: int, hard_end: int) -> int:
    """在 [start, hard_end] 内寻找靠后的句子边界,找不到则返回 hard_end。"""
    window = text[start:hard_end]
    matches = list(_SENTENCE_END.finditer(window))
    if not matches:
        return hard_end
    return start + matches[-1].end()


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """将文本切分为带 overlap 的片段列表。

    参数:
        text: 原始文本。
        chunk_size: 单片段最大字符数(>0)。
        overlap: 相邻片段重叠字符数(0 <= overlap < chunk_size)。

    返回:
        Chunk 列表;空文本返回空列表。

    异常:
        ValueError: 参数非法时抛出。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须满足 0 <= overlap < chunk_size")

    normalized = _normalize(text)
    if not normalized:
        return []

    chunks: list[Chunk] = []
    pos = 0
    length = len(normalized)
    index = 0
    while pos < length:
        hard_end = min(pos + chunk_size, length)
        if hard_end >= length:
            end = hard_end
        else:
            end = _find_break(normalized, pos, hard_end)
        piece = normalized[pos:end].strip()
        if piece:
            chunks.append(Chunk(index=index, text=piece, start=pos, end=end))
            index += 1
        if end >= length:
            break
        # 下一片段起点回退 overlap,保证上下文连续;至少前进 1 防死循环
        pos = max(end - overlap, pos + 1)
    return chunks

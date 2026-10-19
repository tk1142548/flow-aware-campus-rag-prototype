"""Rendering of evidence and dialogue for prompts, shared by every model call."""
from __future__ import annotations

from typing import Sequence


def evidence_block(rows: Sequence[dict]) -> str:
    """Render evidence for a prompt, printing each distinct passage once.

    One passage of an official text is often split into several atomic statements
    that share the same verbatim text. Printing the passage once and listing the
    statements beneath it keeps every id citable without repeating the text.
    """
    if not rows:
        return "（无）"
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row.get("source_id", ""), row.get("verbatim_text", ""))
        groups.setdefault(key, []).append(row)
    blocks = []
    for (_, verbatim), members in groups.items():
        lines = [f"[{m['evidence_id']}] {m.get('normalized_claim', '')}" for m in members]
        lines.append(f"    原文：{verbatim}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def conversation_block(turns: Sequence[dict]) -> str:
    """Render the dialogue so far. A single user turn is shown as the bare question."""
    if len(turns) == 1 and turns[0]["role"] == "user":
        return turns[0]["text"]
    speaker = {"user": "学生", "assistant": "助手"}
    return "\n".join(f"{speaker.get(t['role'], t['role'])}：{t['text']}" for t in turns)

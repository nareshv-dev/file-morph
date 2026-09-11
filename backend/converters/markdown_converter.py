from __future__ import annotations

import re


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>").strip()


def markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    lines.extend(
        "| " + " | ".join(escape_table_cell(cell) for cell in row) + " |"
        for row in normalized[1:]
    )
    return "\n".join(lines)


def normalize_markdown(parts: list[str]) -> str:
    text = "\n\n".join(part.strip() for part in parts if part and part.strip())
    text = "".join(character for character in text if character in "\n\t" or ord(character) >= 0x20)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

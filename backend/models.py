from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Asset:
    filename: str
    content_type: str
    data: bytes
    alt_text: str = "Document image"


@dataclass(slots=True)
class ConversionResult:
    markdown: str
    assets: list[Asset] = field(default_factory=list)
    page_count: int | None = None


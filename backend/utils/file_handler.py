from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator


@contextmanager
def temporary_document(filename: str, data: bytes) -> Iterator[Path]:
    default_root = Path(__file__).resolve().parents[2] / ".markdrop-tmp"
    temp_root = Path(os.getenv("MARKDROP_TMP_DIR", str(default_root)))
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="request-", dir=temp_root) as directory:
        path = Path(directory) / filename
        path.write_bytes(data)
        yield path

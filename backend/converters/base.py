from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Literal


ConversionPayload = bytes | dict[str, object]
ConversionFunction = Callable[[bytes, str], ConversionPayload | Awaitable[ConversionPayload]]


@dataclass(frozen=True, slots=True)
class ConverterDefinition:
    id: str
    title: str
    source_extensions: frozenset[str]
    target_extension: str
    accepted_mime_types: dict[str, frozenset[str]]
    output_mime_type: str
    maximum_file_size: int
    convert: ConversionFunction
    supports_multiple_files: bool = False
    execution: Literal["synchronous", "asynchronous"] = "synchronous"
    fidelity_description: str = ""
    limitations: tuple[str, ...] = ()
    convert_batch: Callable[[list[bytes]], bytes] | None = None
    convert_with_options: Callable[[bytes, dict[str, object]], bytes] | None = None

    def public_metadata(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "source_extensions": sorted(self.source_extensions),
            "accepted_mime_types": {extension: sorted(types) for extension, types in self.accepted_mime_types.items()},
            "target_extension": self.target_extension,
            "output_mime_type": self.output_mime_type,
            "maximum_file_size": self.maximum_file_size,
            "supports_multiple_files": self.supports_multiple_files,
            "execution": self.execution,
            "fidelity_description": self.fidelity_description,
            "limitations": list(self.limitations),
        }

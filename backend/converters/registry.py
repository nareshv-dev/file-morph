from __future__ import annotations

from backend.converters.base import ConverterDefinition


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: dict[str, ConverterDefinition] = {}

    def register(self, converter: ConverterDefinition) -> ConverterDefinition:
        if converter.id in self._converters:
            raise ValueError(f"Converter '{converter.id}' is already registered.")
        self._converters[converter.id] = converter
        return converter

    def get(self, converter_id: str) -> ConverterDefinition | None:
        return self._converters.get(converter_id)

    def require(self, converter_id: str) -> ConverterDefinition:
        converter = self.get(converter_id)
        if converter is None:
            raise KeyError(converter_id)
        return converter

    def all(self) -> tuple[ConverterDefinition, ...]:
        return tuple(self._converters.values())

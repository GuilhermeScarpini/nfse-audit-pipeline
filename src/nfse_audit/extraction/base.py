"""Extraction interface: turns a document (bytes) into a domain Invoice.

Each format (national XML today, PDF in the future) is one implementation of
InvoiceExtractor. The pipeline only knows this interface, so adding a format
means adding a class, not changing the pipeline.
"""

from collections.abc import Sequence
from typing import Protocol

from nfse_audit.domain import Invoice


class ExtractionError(ValueError):
    """The document could not be turned into an invoice."""


class InvoiceExtractor(Protocol):
    name: str

    def supports(self, filename: str, content: bytes) -> bool: ...

    def extract(self, content: bytes) -> Invoice: ...


class ExtractorRegistry:
    def __init__(self, extractors: Sequence[InvoiceExtractor]) -> None:
        self._extractors = tuple(extractors)

    def extract(self, filename: str, content: bytes) -> Invoice:
        for extractor in self._extractors:
            if extractor.supports(filename, content):
                return extractor.extract(content)
        raise ExtractionError(f"unsupported document format: {filename}")

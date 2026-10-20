"""Orchestrates extraction -> rules -> report. Used by the CLI and by the worker."""

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from nfse_audit.extraction.base import ExtractionError, ExtractorRegistry
from nfse_audit.reporting.models import BatchReport, DocumentError
from nfse_audit.rules.engine import RuleEngine
from nfse_audit.rules.results import InvoiceAudit

Document = tuple[str, bytes]
"""(filename, content)"""


def audit_documents(
    batch_id: str,
    documents: Iterable[Document],
    extractors: ExtractorRegistry,
    engine: RuleEngine,
) -> BatchReport:
    audits: list[InvoiceAudit] = []
    errors: list[DocumentError] = []
    seen_content: dict[str, str] = {}
    seen_keys: dict[str, str] = {}

    for filename, content in documents:
        digest = hashlib.sha256(content).hexdigest()
        if digest in seen_content:
            errors.append(
                DocumentError(source=filename, message=f"duplicate of {seen_content[digest]}")
            )
            continue
        seen_content[digest] = filename
        try:
            invoice = extractors.extract(filename, content)
        except ExtractionError as exc:
            errors.append(DocumentError(source=filename, message=str(exc)))
            continue
        if (first := seen_keys.get(invoice.access_key)) is not None:
            message = f"invoice {invoice.access_key} already audited from {first}"
            errors.append(DocumentError(source=filename, message=message))
            continue
        seen_keys[invoice.access_key] = filename
        audits.append(engine.audit(invoice))

    return BatchReport(
        batch_id=batch_id, generated_at=datetime.now(UTC), invoices=audits, errors=errors
    )

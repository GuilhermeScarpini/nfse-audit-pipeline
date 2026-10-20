"""Worker job. RQ imports `process_batch` by its dotted path and calls it.

Delivery is at-least-once: a job may run again after a crash or a retry, so it is
idempotent by design. It reads the same inputs and overwrites the same report.
"""

import logging

from redis import Redis

from nfse_audit.config import get_settings
from nfse_audit.extraction import ExtractorRegistry
from nfse_audit.pipeline import audit_documents
from nfse_audit.reporting import to_json
from nfse_audit.rules.engine import RuleEngine
from nfse_audit.storage import BatchFileStore, BatchState, BatchStatusStore
from nfse_audit.tax_tables import TaxTables

logger = logging.getLogger(__name__)


def run_batch(
    batch_id: str,
    status_store: BatchStatusStore,
    file_store: BatchFileStore,
    extractors: ExtractorRegistry,
    engine: RuleEngine,
) -> None:
    status_store.update(batch_id, BatchState.PROCESSING)
    try:
        report = audit_documents(batch_id, file_store.iter_inputs(batch_id), extractors, engine)
        file_store.save_report(batch_id, to_json(report))
    except Exception as exc:
        logger.exception("batch %s failed", batch_id)
        status_store.update(batch_id, BatchState.FAILED, error=str(exc))
        raise
    status_store.update(batch_id, BatchState.DONE, summary=report.summary)


def default_extractors() -> ExtractorRegistry:
    from nfse_audit.extraction.national_xml import NationalXmlExtractor

    return ExtractorRegistry([NationalXmlExtractor()])


def process_batch(batch_id: str) -> None:
    """Entry point executed by the RQ worker: builds real dependencies from settings."""
    settings = get_settings()
    run_batch(
        batch_id,
        BatchStatusStore(Redis.from_url(settings.redis_url)),
        BatchFileStore(settings.data_dir),
        default_extractors(),
        RuleEngine(TaxTables.from_directory()),
    )

from nfse_audit.reporting.models import BatchReport


def to_json(report: BatchReport) -> str:
    """Decimals are serialized as strings, so no value loses precision as a float."""
    return report.model_dump_json(indent=2)

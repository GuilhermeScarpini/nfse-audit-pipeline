from collections import Counter
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from nfse_audit.rules.results import InvoiceAudit, RuleStatus


class DocumentError(BaseModel):
    """A document that could not be audited (unreadable, unsupported, duplicate)."""

    model_config = ConfigDict(frozen=True)

    source: str
    message: str


class BatchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str
    generated_at: datetime
    invoices: list[InvoiceAudit]
    errors: list[DocumentError] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> dict[str, int]:
        by_status = Counter(audit.status.value for audit in self.invoices)
        return {
            "documents": len(self.invoices) + len(self.errors),
            "invoices_audited": len(self.invoices),
            "documents_with_errors": len(self.errors),
            **{f"invoices_{status.value}": by_status.get(status.value, 0) for status in _SUMMARY},
        }


_SUMMARY = (RuleStatus.OK, RuleStatus.DIVERGENT, RuleStatus.ERROR)

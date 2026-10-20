from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RuleStatus(StrEnum):
    OK = "ok"
    DIVERGENT = "divergent"
    NOT_APPLICABLE = "not_applicable"
    """The rule does not apply to this invoice (e.g. IRRF for a Simples Nacional provider)."""
    ERROR = "error"
    """The rule could not be evaluated (e.g. no tax table covers the municipality)."""


class RuleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    description: str
    status: RuleStatus
    expected: Decimal | None = None
    found: Decimal | None = None
    detail: str = ""
    legal_basis: str | None = None
    table_id: str | None = None
    table_version: str | None = None
    """Interval of the tax table version applied, e.g. "2026-01-01..2026-12-31"."""
    table_verified: bool | None = None


class InvoiceAudit(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_key: str
    number: str
    competence_date: date
    provider_cnpj: str
    taker_cnpj: str
    service_amount: Decimal
    results: list[RuleResult]

    @property
    def status(self) -> RuleStatus:
        statuses = {result.status for result in self.results}
        for status in (RuleStatus.ERROR, RuleStatus.DIVERGENT):
            if status in statuses:
                return status
        return RuleStatus.OK

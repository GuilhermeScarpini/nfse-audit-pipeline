"""Building blocks for rules.

A rule is a pure function (invoice, tables) -> Outcome: no I/O, no clock, no
randomness. Given the same invoice and tables it always gives the same answer,
which is what makes an audit reproducible.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from nfse_audit.domain import Invoice
from nfse_audit.domain.types import CENT
from nfse_audit.rules.results import RuleStatus
from nfse_audit.tax_tables import TableVersion, TaxTables

ZERO = Decimal("0.00")
AMOUNT_TOLERANCE = CENT
"""Differences up to one cent are accepted: issuers may round or truncate."""


@dataclass(frozen=True)
class Outcome:
    status: RuleStatus
    expected: Decimal | None = None
    found: Decimal | None = None
    detail: str = ""
    legal_basis: str | None = None
    table_id: str | None = None
    table: TableVersion | None = None


RuleFunc = Callable[[Invoice, TaxTables], Outcome]


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    func: RuleFunc

    def __call__(self, invoice: Invoice, tables: TaxTables) -> Outcome:
        return self.func(invoice, tables)


def rule(id: str, description: str) -> Callable[[RuleFunc], Rule]:
    def decorator(func: RuleFunc) -> Rule:
        return Rule(id=id, description=description, func=func)

    return decorator


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def percent(rate: Decimal) -> str:
    return f"{(rate * 100).normalize():f}%"


def compare(
    expected: Decimal,
    found: Decimal,
    *,
    tolerance: Decimal = AMOUNT_TOLERANCE,
    detail: str = "",
    legal_basis: str | None = None,
    table_id: str | None = None,
    table: TableVersion | None = None,
) -> Outcome:
    status = RuleStatus.OK if abs(expected - found) <= tolerance else RuleStatus.DIVERGENT
    return Outcome(status, expected, found, detail, legal_basis or _basis(table), table_id, table)


def not_applicable_unless_charged(
    found: Decimal,
    detail: str,
    *,
    legal_basis: str | None = None,
    table_id: str | None = None,
    table: TableVersion | None = None,
) -> Outcome:
    """The tax does not apply; it is still a divergence if something was charged anyway."""
    if found > ZERO:
        return Outcome(
            RuleStatus.DIVERGENT,
            ZERO,
            found,
            f"{detail}; nothing should have been charged",
            legal_basis or _basis(table),
            table_id,
            table,
        )
    return Outcome(
        RuleStatus.NOT_APPLICABLE,
        None,
        found,
        detail,
        legal_basis or _basis(table),
        table_id,
        table,
    )


def _basis(table: TableVersion | None) -> str | None:
    return table.legal_basis if table else None

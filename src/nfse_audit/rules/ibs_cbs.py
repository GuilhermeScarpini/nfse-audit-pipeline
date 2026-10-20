"""IBS and CBS highlighted on the invoice (tax reform, LC 214/2025)."""

from decimal import Decimal
from typing import Literal

from nfse_audit.domain import Invoice
from nfse_audit.rules.base import Outcome, Rule, compare, percent, rule, to_cents
from nfse_audit.rules.results import RuleStatus
from nfse_audit.tax_tables import TaxTables

SIMPLES_BASIS = "LC 214/2025 (Simples Nacional: IBS/CBS recolhidos no regime do Simples)"
TABLE_ID = "ibs_cbs"

Component = Literal["cbs", "ibs_state", "ibs_municipal"]


def _ibs_cbs_rule(component: Component) -> Rule:
    @rule(f"{component.upper()}_AMOUNT", f"{component.upper()} amount highlighted on the invoice")
    def check(invoice: Invoice, tables: TaxTables) -> Outcome:
        table = tables.ibs_cbs(invoice.competence_date)
        rate: Decimal = getattr(table.params, f"{component}_rate")
        info = invoice.ibs_cbs
        if invoice.provider.is_simples_nacional:
            return Outcome(
                RuleStatus.NOT_APPLICABLE,
                detail="Simples Nacional provider",
                legal_basis=SIMPLES_BASIS,
            )
        if info is None:
            expected = to_cents(invoice.service_amount * rate)
            if table.params.mandatory:
                return Outcome(
                    RuleStatus.DIVERGENT,
                    expected=expected,
                    detail="IBS/CBS group missing; it is mandatory in this period",
                    legal_basis=table.legal_basis,
                    table_id=TABLE_ID,
                    table=table,
                )
            return Outcome(
                RuleStatus.NOT_APPLICABLE,
                detail="IBS/CBS not highlighted; optional in this period",
                legal_basis=table.legal_basis,
                table_id=TABLE_ID,
                table=table,
            )
        declared_rate: Decimal = getattr(info, f"{component}_rate")
        found: Decimal = getattr(info, f"{component}_amount")
        detail = f"{info.base} x {percent(rate)}"
        if declared_rate != rate:
            detail += f"; declared rate {percent(declared_rate)} differs from the table"
        return compare(
            to_cents(info.base * rate), found, detail=detail, table_id=TABLE_ID, table=table
        )

    return check


cbs_amount = _ibs_cbs_rule("cbs")
ibs_state_amount = _ibs_cbs_rule("ibs_state")
ibs_municipal_amount = _ibs_cbs_rule("ibs_municipal")

RULES = (cbs_amount, ibs_state_amount, ibs_municipal_amount)

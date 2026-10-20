"""IBS and CBS highlighted on the invoice (tax reform, LC 214/2025)."""

from decimal import Decimal
from typing import Literal

from nfse_audit.domain import Invoice
from nfse_audit.rules.base import ZERO, Outcome, Rule, compare, percent, rule, to_cents
from nfse_audit.rules.results import RuleStatus
from nfse_audit.tax_tables import TableVersion, TaxTables
from nfse_audit.tax_tables.models import IbsCbs

SIMPLES_BASIS = (
    "LC 214/2025, art. 348, III, c (2026); from 2027 Simples Nacional IBS/CBS go in the "
    "gTribSN group (NT 009), outside the scope of this project"
)
TABLE_ID = "ibs_cbs"

Component = Literal["cbs", "ibs_state", "ibs_municipal"]


def _outcome(status: RuleStatus, table: TableVersion[IbsCbs], **fields) -> Outcome:
    return Outcome(status, legal_basis=table.legal_basis, table_id=TABLE_ID, table=table, **fields)


def expected_base(invoice: Invoice, params: IbsCbs) -> Decimal:
    pis_cofins = invoice.pis_cofins
    deductions = {
        "iss": invoice.iss.amount,
        "pis": pis_cofins.pis_amount if pis_cofins else ZERO,
        "cofins": pis_cofins.cofins_amount if pis_cofins else ZERO,
    }
    return invoice.service_amount - sum((deductions[d] for d in params.base_deductions), ZERO)


def _ibs_cbs_rule(component: Component) -> Rule:
    @rule(f"{component.upper()}_AMOUNT", f"{component.upper()} amount highlighted on the invoice")
    def check(invoice: Invoice, tables: TaxTables) -> Outcome:
        if invoice.provider.is_simples_nacional:
            return Outcome(
                RuleStatus.NOT_APPLICABLE,
                detail="Simples Nacional provider",
                legal_basis=SIMPLES_BASIS,
            )
        table = tables.ibs_cbs(invoice.competence_date)
        params = table.params
        rate: Decimal | None = getattr(params, f"{component}_rate")
        info = invoice.ibs_cbs
        subitem = invoice.service.lc116_subitem
        if info is None:
            if not params.is_mandatory_for(subitem):
                return _outcome(
                    RuleStatus.NOT_APPLICABLE,
                    table,
                    detail=f"IBS/CBS not highlighted; optional for subitem {subitem} for now",
                )
            return _outcome(
                RuleStatus.DIVERGENT,
                table,
                expected=None if rate is None else to_cents(expected_base(invoice, params) * rate),
                detail="IBS/CBS group missing; it is mandatory in this period",
            )
        found: Decimal = getattr(info, f"{component}_amount")
        if rate is None:
            return _outcome(
                RuleStatus.ERROR,
                table,
                found=found,
                detail="rate not yet published for this period (CBS reference rate pending)",
            )
        declared_rate: Decimal = getattr(info, f"{component}_rate")
        detail = f"{info.base} x {percent(rate)}"
        if declared_rate != rate:
            detail += f"; declared rate {percent(declared_rate)} differs from the table"
        return compare(
            to_cents(info.base * rate), found, detail=detail, table_id=TABLE_ID, table=table
        )

    return check


@rule("IBS_CBS_BASE", "IBS/CBS base equals the service value minus the deductions in force")
def ibs_cbs_base(invoice: Invoice, tables: TaxTables) -> Outcome:
    info = invoice.ibs_cbs
    if info is None or invoice.provider.is_simples_nacional:
        return Outcome(RuleStatus.NOT_APPLICABLE, detail="no IBS/CBS group to check")
    table = tables.ibs_cbs(invoice.competence_date)
    deductions = ", ".join(table.params.base_deductions)
    return compare(
        expected_base(invoice, table.params),
        info.base,
        detail=f"service value minus {deductions}",
        legal_basis="Layout NFS-e v1.01 (NT 004), fórmula de vBC do grupo IBSCBS",
        table_id=TABLE_ID,
        table=table,
    )


cbs_amount = _ibs_cbs_rule("cbs")
ibs_state_amount = _ibs_cbs_rule("ibs_state")
ibs_municipal_amount = _ibs_cbs_rule("ibs_municipal")

RULES = (ibs_cbs_base, cbs_amount, ibs_state_amount, ibs_municipal_amount)

from nfse_audit.domain import Invoice
from nfse_audit.rules.base import (
    ZERO,
    Outcome,
    compare,
    not_applicable_unless_charged,
    percent,
    rule,
    to_cents,
)
from nfse_audit.tax_tables import TaxTables

SIMPLES_BASIS = "IN RFB 765/2007 (sem retenção de IRRF para optantes do Simples Nacional)"


@rule("IRRF_WITHHOLDING", "IRRF withheld according to the service type")
def irrf_withholding(invoice: Invoice, tables: TaxTables) -> Outcome:
    found = invoice.withholdings.irrf
    table = tables.irrf(invoice.competence_date)
    if invoice.provider.is_simples_nacional:
        return not_applicable_unless_charged(
            found, "Simples Nacional provider", legal_basis=SIMPLES_BASIS
        )
    subitem = invoice.service.lc116_subitem
    group = table.params.rate_for(subitem)
    if group is None:
        return not_applicable_unless_charged(
            found, f"subitem {subitem} not subject to IRRF", table_id="irrf", table=table
        )
    expected = to_cents(invoice.service_amount * group.rate)
    detail = f"{invoice.service_amount} x {percent(group.rate)} ({group.name})"
    if expected <= table.params.min_amount:
        expected = ZERO
        detail += f"; waived: at most R$ {table.params.min_amount}"
    return compare(expected, found, detail=detail, table_id="irrf", table=table)


RULES = (irrf_withholding,)

"""PIS, COFINS and CSLL withheld at source (Lei 10.833/2003, art. 30).

The waiver threshold applies to the SUM of the taxes withheld in the period, so
each rule looks at the whole table version, not only at its own tax.
"""

from nfse_audit.domain import Invoice
from nfse_audit.rules.base import (
    ZERO,
    Outcome,
    Rule,
    compare,
    not_applicable_unless_charged,
    percent,
    rule,
    to_cents,
)
from nfse_audit.tax_tables import TaxTables
from nfse_audit.tax_tables.models import WithheldTax

SIMPLES_BASIS = "Lei 10.833/2003, art. 32, III (sem retenção para optantes do Simples Nacional)"
TABLE_ID = "federal_withholding"


def _withholding_rule(tax: WithheldTax) -> Rule:
    @rule(f"{tax.upper()}_WITHHOLDING", f"{tax.upper()} withheld at source")
    def check(invoice: Invoice, tables: TaxTables) -> Outcome:
        found = getattr(invoice.withholdings, tax)
        table = tables.federal_withholding(invoice.competence_date)
        params = table.params
        if invoice.provider.is_simples_nacional:
            return not_applicable_unless_charged(
                found, "Simples Nacional provider", legal_basis=SIMPLES_BASIS
            )
        if tax not in params.rates:
            return not_applicable_unless_charged(
                found, f"{tax.upper()} not withheld in this period", table_id=TABLE_ID, table=table
            )
        subitem = invoice.service.lc116_subitem
        if subitem not in params.subitems:
            return not_applicable_unless_charged(
                found,
                f"subitem {subitem} not subject to withholding",
                table_id=TABLE_ID,
                table=table,
            )
        amounts = {
            name: to_cents(invoice.service_amount * rate) for name, rate in params.rates.items()
        }
        expected = amounts[tax]
        detail = f"{invoice.service_amount} x {percent(params.rates[tax])}"
        total = sum(amounts.values(), ZERO)
        if total <= params.min_total:
            expected = ZERO
            detail += f"; waived: total withheld {total} is at most R$ {params.min_total}"
        return compare(expected, found, detail=detail, table_id=TABLE_ID, table=table)

    return check


pis_withholding = _withholding_rule("pis")
cofins_withholding = _withholding_rule("cofins")
csll_withholding = _withholding_rule("csll")

RULES = (pis_withholding, cofins_withholding, csll_withholding)

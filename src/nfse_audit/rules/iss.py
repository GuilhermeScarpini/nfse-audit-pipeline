from decimal import Decimal

from nfse_audit.domain import Invoice, SimplesNacionalOption
from nfse_audit.rules.base import Outcome, compare, percent, rule, to_cents
from nfse_audit.rules.results import RuleStatus
from nfse_audit.tax_tables import TaxTables

MEI_BASIS = "LC 123/2006, art. 18-A (MEI recolhe ISS em valor fixo no DAS)"
SIMPLES_BASIS = "LC 123/2006, art. 18 (alíquota do Simples depende da faixa de receita)"


@rule("ISS_RATE_RANGE", "ISS rate within the national limits")
def iss_rate_range(invoice: Invoice, tables: TaxTables) -> Outcome:
    if invoice.provider.simples_nacional is SimplesNacionalOption.MEI:
        return Outcome(RuleStatus.NOT_APPLICABLE, detail="MEI provider", legal_basis=MEI_BASIS)
    table = tables.iss_limits(invoice.competence_date)
    limits = table.params
    subitem = invoice.service.lc116_subitem
    minimum = Decimal(0) if subitem in limits.below_min_allowed_subitems else limits.min_rate
    rate = invoice.iss.rate
    within = minimum <= rate <= limits.max_rate
    return Outcome(
        RuleStatus.OK if within else RuleStatus.DIVERGENT,
        found=rate,
        detail=f"expected between {percent(minimum)} and {percent(limits.max_rate)}",
        legal_basis=table.legal_basis,
        table_id="iss_limits",
        table=table,
    )


@rule("ISS_RATE_MUNICIPAL", "ISS rate matches the municipal table for the service")
def iss_rate_municipal(invoice: Invoice, tables: TaxTables) -> Outcome:
    if invoice.provider.is_simples_nacional:
        return Outcome(
            RuleStatus.NOT_APPLICABLE, detail="Simples Nacional provider", legal_basis=SIMPLES_BASIS
        )
    municipality = invoice.service.incidence_municipality_code
    table = tables.municipal_iss(municipality, invoice.competence_date)
    subitem = invoice.service.lc116_subitem
    expected = table.params.rates.get(subitem)
    if expected is None:
        return Outcome(
            RuleStatus.ERROR,
            found=invoice.iss.rate,
            detail=f"no rate for subitem {subitem} in municipality {municipality}",
            table_id=f"iss_{municipality}",
            table=table,
        )
    return compare(
        expected,
        invoice.iss.rate,
        tolerance=Decimal(0),
        detail=f"subitem {subitem}, {table.params.municipality_name}",
        table_id=f"iss_{municipality}",
        table=table,
    )


@rule("ISS_AMOUNT", "ISS amount equals base times rate")
def iss_amount(invoice: Invoice, tables: TaxTables) -> Outcome:
    if invoice.provider.simples_nacional is SimplesNacionalOption.MEI:
        return Outcome(RuleStatus.NOT_APPLICABLE, detail="MEI provider", legal_basis=MEI_BASIS)
    iss = invoice.iss
    return compare(
        to_cents(iss.base * iss.rate),
        iss.amount,
        detail=f"{iss.base} x {percent(iss.rate)}",
        legal_basis="LC 116/2003, art. 7º (base de cálculo é o preço do serviço)",
    )


RULES = (iss_rate_range, iss_rate_municipal, iss_amount)

from datetime import date
from decimal import Decimal

import pytest

from nfse_audit.domain import SimplesNacionalOption
from nfse_audit.rules.ibs_cbs import (
    cbs_amount,
    ibs_cbs_base,
    ibs_municipal_amount,
    ibs_state_amount,
)
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import (
    make_ibs_cbs,
    make_invoice,
    make_iss,
    make_provider,
    make_service,
    make_withholdings,
)

BEFORE_MANDATORY = date(2026, 6, 1)
OCTOBER_2026 = date(2026, 10, 1)
DECEMBER_2026 = date(2026, 12, 1)
YEAR_2027 = date(2027, 3, 1)


def _invoice_2027(**overrides):
    """2027: no PIS/COFINS, only CSLL withheld; R$ 2000.00 so CSLL is above the waiver."""
    data = {
        "competence_date": YEAR_2027,
        "service_amount": Decimal("2000.00"),
        "iss": make_iss(base="2000.00"),
        "withholdings": make_withholdings(irrf="30.00", csll="20.00"),
        "pis_cofins": None,
    }
    return make_invoice(**(data | overrides))


def test_2026_highlight_is_ok_with_base_net_of_iss_pis_cofins(tables):
    # 1000.00 - ISS 50.00 - PIS 6.50 - COFINS 30.00 = 913.50
    invoice = make_invoice(
        competence_date=OCTOBER_2026,
        ibs_cbs=make_ibs_cbs(
            "913.50", cbs_rate="0.009", ibs_state_rate="0.001", ibs_municipal_rate="0"
        ),
    )
    for rule in (ibs_cbs_base, cbs_amount, ibs_state_amount, ibs_municipal_amount):
        assert rule(invoice, tables).status is RuleStatus.OK, rule.id


def test_2026_has_no_municipal_ibs(tables):
    invoice = make_invoice(
        competence_date=OCTOBER_2026,
        ibs_cbs=make_ibs_cbs(
            "913.50", cbs_rate="0.009", ibs_state_rate="0.0005", ibs_municipal_rate="0.0005"
        ),
    )
    assert ibs_municipal_amount(invoice, tables).status is RuleStatus.DIVERGENT
    assert ibs_state_amount(invoice, tables).status is RuleStatus.DIVERGENT


def test_base_without_deductions_is_divergent(tables):
    invoice = make_invoice(
        competence_date=OCTOBER_2026,
        ibs_cbs=make_ibs_cbs(
            "1000.00", cbs_rate="0.009", ibs_state_rate="0.001", ibs_municipal_rate="0"
        ),
    )
    outcome = ibs_cbs_base(invoice, tables)
    assert (outcome.status, outcome.expected) == (RuleStatus.DIVERGENT, Decimal("913.50"))


@pytest.mark.parametrize(
    ("competence", "service_code", "status"),
    [
        (BEFORE_MANDATORY, "170101", RuleStatus.NOT_APPLICABLE),  # optional before October
        (OCTOBER_2026, "170101", RuleStatus.DIVERGENT),  # mandatory for general services
        (OCTOBER_2026, "010501", RuleStatus.NOT_APPLICABLE),  # 1.05 only from December
        (DECEMBER_2026, "010501", RuleStatus.DIVERGENT),
    ],
)
def test_missing_group_depends_on_date_and_subitem(tables, competence, service_code, status):
    invoice = make_invoice(competence_date=competence, service=make_service(code=service_code))
    assert cbs_amount(invoice, tables).status is status


def test_2027_base_deducts_only_iss(tables):
    invoice = _invoice_2027(
        ibs_cbs=make_ibs_cbs(
            "1900.00", cbs_rate="0.088", ibs_state_rate="0.0005", ibs_municipal_rate="0.0005"
        ),
    )
    assert ibs_cbs_base(invoice, tables).status is RuleStatus.OK  # 2000.00 - ISS 100.00


def test_2027_ibs_split_between_state_and_municipality(tables):
    invoice = _invoice_2027(
        ibs_cbs=make_ibs_cbs(
            "1900.00", cbs_rate="0.088", ibs_state_rate="0.0005", ibs_municipal_rate="0.0005"
        ),
    )
    assert ibs_state_amount(invoice, tables).status is RuleStatus.OK
    assert ibs_municipal_amount(invoice, tables).status is RuleStatus.OK


def test_2027_cbs_is_an_error_until_the_reference_rate_is_published(tables):
    assert tables.ibs_cbs(YEAR_2027).params.cbs_rate is None
    invoice = _invoice_2027(
        ibs_cbs=make_ibs_cbs(
            "1900.00", cbs_rate="0.088", ibs_state_rate="0.0005", ibs_municipal_rate="0.0005"
        ),
    )
    outcome = cbs_amount(invoice, tables)
    assert outcome.status is RuleStatus.ERROR
    assert "not yet published" in outcome.detail


def test_2026_rates_on_a_2027_invoice_are_divergent(tables):
    invoice = _invoice_2027(
        ibs_cbs=make_ibs_cbs(
            "1900.00", cbs_rate="0.009", ibs_state_rate="0.001", ibs_municipal_rate="0"
        ),
    )
    outcome = ibs_state_amount(invoice, tables)
    assert outcome.status is RuleStatus.DIVERGENT
    assert "differs from the table" in outcome.detail


def test_simples_provider_not_applicable(tables):
    invoice = _invoice_2027(provider=make_provider(simples=SimplesNacionalOption.ME_EPP))
    assert cbs_amount(invoice, tables).status is RuleStatus.NOT_APPLICABLE
    assert ibs_cbs_base(invoice, tables).status is RuleStatus.NOT_APPLICABLE

from datetime import date
from decimal import Decimal

import pytest

from nfse_audit.domain import SimplesNacionalOption
from nfse_audit.rules.federal_withholding import (
    cofins_withholding,
    csll_withholding,
    pis_withholding,
)
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import (
    make_invoice,
    make_provider,
    make_service,
    make_withholdings,
)

COMPETENCE_2027 = date(2027, 3, 1)


@pytest.mark.parametrize(
    ("rule", "expected"),
    [(pis_withholding, "6.50"), (cofins_withholding, "30.00"), (csll_withholding, "10.00")],
)
def test_withholding_2026(tables, rule, expected):
    outcome = rule(make_invoice(), tables)
    assert (outcome.status, outcome.expected) == (RuleStatus.OK, Decimal(expected))


def test_wrong_cofins_is_divergent(tables):
    invoice = make_invoice(
        withholdings=make_withholdings(irrf="15.00", pis="6.50", cofins="3.00", csll="10.00")
    )
    assert cofins_withholding(invoice, tables).status is RuleStatus.DIVERGENT


def test_waiver_uses_the_sum_of_the_three_taxes(tables):
    # R$ 215.00 x 4.65% = 10.00 in total -> waived, even though each tax is smaller
    invoice = make_invoice(service_amount=Decimal("215.00"), withholdings=make_withholdings())
    for rule in (pis_withholding, cofins_withholding, csll_withholding):
        outcome = rule(invoice, tables)
        assert (outcome.status, outcome.expected) == (RuleStatus.OK, Decimal("0.00"))


@pytest.mark.parametrize("rule", [pis_withholding, cofins_withholding])
def test_pis_and_cofins_not_withheld_from_2027(tables, rule):
    invoice = make_invoice(
        competence_date=COMPETENCE_2027, withholdings=make_withholdings(csll="10.00")
    )
    assert rule(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_pis_withheld_in_2027_is_divergent(tables):
    invoice = make_invoice(competence_date=COMPETENCE_2027)  # still withholds PIS/COFINS
    outcome = pis_withholding(invoice, tables)
    assert (outcome.status, outcome.expected, outcome.found) == (
        RuleStatus.DIVERGENT,
        Decimal("0.00"),
        Decimal("6.50"),
    )


def test_csll_still_withheld_in_2027(tables):
    invoice = make_invoice(
        competence_date=COMPETENCE_2027,
        service_amount=Decimal("2000.00"),
        withholdings=make_withholdings(csll="20.00"),
    )
    assert csll_withholding(invoice, tables).status is RuleStatus.OK


def test_same_service_withheld_in_2026_is_waived_in_2027(tables):
    # R$ 1000.00: in 2026 PIS+COFINS+CSLL = 46.50 (withheld); in 2027 CSLL alone
    # is 10.00, which is at most the R$ 10 threshold, so nothing is withheld.
    invoice_2026 = make_invoice()
    invoice_2027 = make_invoice(competence_date=COMPETENCE_2027, withholdings=make_withholdings())
    assert csll_withholding(invoice_2026, tables).expected == Decimal("10.00")
    outcome_2027 = csll_withholding(invoice_2027, tables)
    assert (outcome_2027.status, outcome_2027.expected) == (RuleStatus.OK, Decimal("0.00"))


def test_simples_provider_has_no_withholding(tables):
    invoice = make_invoice(
        provider=make_provider(simples=SimplesNacionalOption.ME_EPP),
        withholdings=make_withholdings(),
    )
    assert csll_withholding(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_service_not_subject_to_withholding(tables):
    invoice = make_invoice(service=make_service(code="010501"), withholdings=make_withholdings())
    assert pis_withholding(invoice, tables).status is RuleStatus.NOT_APPLICABLE

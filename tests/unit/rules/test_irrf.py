from decimal import Decimal

import pytest

from nfse_audit.domain import SimplesNacionalOption
from nfse_audit.rules.irrf import irrf_withholding
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import (
    make_invoice,
    make_iss,
    make_provider,
    make_service,
    make_withholdings,
)


def test_professional_service_withholds_1_5_percent(tables):
    outcome = irrf_withholding(make_invoice(), tables)
    assert outcome.status is RuleStatus.OK
    assert outcome.expected == Decimal("15.00")


def test_missing_irrf_is_divergent(tables):
    invoice = make_invoice(withholdings=make_withholdings(irrf="0"))
    outcome = irrf_withholding(invoice, tables)
    assert (outcome.status, outcome.expected, outcome.found) == (
        RuleStatus.DIVERGENT,
        Decimal("15.00"),
        Decimal("0.00"),
    )


def test_cleaning_service_withholds_1_percent(tables):
    invoice = make_invoice(
        service=make_service(code="071001"),
        iss=make_iss(rate="0.03"),
        withholdings=make_withholdings(irrf="10.01"),
        service_amount=Decimal("1001.00"),
    )
    assert irrf_withholding(invoice, tables).expected == Decimal("10.01")


@pytest.mark.parametrize(("amount", "expected"), [("666.00", "0.00"), ("667.00", "10.01")])
def test_irrf_waived_at_or_below_ten_reais(tables, amount, expected):
    # 1.5% of 666.00 = 9.99 (waived); 1.5% of 667.00 = 10.005 -> 10.01
    invoice = make_invoice(service_amount=Decimal(amount))
    assert irrf_withholding(invoice, tables).expected == Decimal(expected)


def test_simples_provider_irrf_not_applicable(tables):
    invoice = make_invoice(
        provider=make_provider(simples=SimplesNacionalOption.ME_EPP),
        withholdings=make_withholdings(),
    )
    assert irrf_withholding(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_irrf_withheld_from_simples_provider_is_divergent(tables):
    invoice = make_invoice(provider=make_provider(simples=SimplesNacionalOption.ME_EPP))
    outcome = irrf_withholding(invoice, tables)
    assert (outcome.status, outcome.expected) == (RuleStatus.DIVERGENT, Decimal("0.00"))


def test_service_not_subject_to_irrf(tables):
    invoice = make_invoice(service=make_service(code="010501"), withholdings=make_withholdings())
    assert irrf_withholding(invoice, tables).status is RuleStatus.NOT_APPLICABLE

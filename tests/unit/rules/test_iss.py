from datetime import date
from decimal import Decimal

import pytest

from nfse_audit.domain import SimplesNacionalOption
from nfse_audit.rules.iss import iss_amount, iss_rate_municipal, iss_rate_range
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import make_invoice, make_iss, make_provider, make_service


@pytest.mark.parametrize(
    ("rate", "status"),
    [
        ("0.02", RuleStatus.OK),
        ("0.05", RuleStatus.OK),
        ("0.019", RuleStatus.DIVERGENT),
        ("0.06", RuleStatus.DIVERGENT),
    ],
)
def test_iss_rate_range(tables, rate, status):
    invoice = make_invoice(iss=make_iss(rate=rate))
    assert iss_rate_range(invoice, tables).status is status


def test_iss_rate_below_minimum_allowed_for_exempt_subitem(tables):
    invoice = make_invoice(service=make_service(code="070201"), iss=make_iss(rate="0.01"))
    assert iss_rate_range(invoice, tables).status is RuleStatus.OK


def test_iss_rules_do_not_apply_to_mei(tables):
    invoice = make_invoice(provider=make_provider(simples=SimplesNacionalOption.MEI))
    assert iss_rate_range(invoice, tables).status is RuleStatus.NOT_APPLICABLE
    assert iss_amount(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_iss_rate_matches_municipal_table(tables):
    assert iss_rate_municipal(make_invoice(), tables).status is RuleStatus.OK


def test_iss_rate_different_from_municipal_table(tables):
    outcome = iss_rate_municipal(make_invoice(iss=make_iss(rate="0.03")), tables)
    assert outcome.status is RuleStatus.DIVERGENT
    assert (outcome.expected, outcome.found) == (Decimal("0.05"), Decimal("0.03"))


@pytest.mark.parametrize(
    ("competence", "rate", "status"),
    [
        (date(2026, 12, 1), "0.02", RuleStatus.OK),
        (date(2027, 1, 1), "0.02", RuleStatus.DIVERGENT),  # synthetic rate went up to 2.5%
        (date(2027, 1, 1), "0.025", RuleStatus.OK),
    ],
)
def test_municipal_rate_follows_the_competence_date(tables, competence, rate, status):
    invoice = make_invoice(
        competence_date=competence,
        service=make_service(code="010501"),
        iss=make_iss(rate=rate),
    )
    assert iss_rate_municipal(invoice, tables).status is status


def test_iss_municipal_rate_not_applicable_to_simples(tables):
    invoice = make_invoice(provider=make_provider(simples=SimplesNacionalOption.ME_EPP))
    assert iss_rate_municipal(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_iss_municipal_rate_error_when_subitem_missing(tables):
    invoice = make_invoice(service=make_service(code="990101"))
    assert iss_rate_municipal(invoice, tables).status is RuleStatus.ERROR


@pytest.mark.parametrize(
    ("amount", "status"),
    [
        ("50.00", RuleStatus.OK),
        ("50.01", RuleStatus.OK),  # one cent of tolerance
        ("49.98", RuleStatus.DIVERGENT),
    ],
)
def test_iss_amount(tables, amount, status):
    assert iss_amount(make_invoice(iss=make_iss(amount=amount)), tables).status is status

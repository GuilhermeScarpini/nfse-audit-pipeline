"""Expected values come from the tables, so these tests survive rate updates."""

from datetime import date
from decimal import Decimal

import pytest

from nfse_audit.domain import SimplesNacionalOption
from nfse_audit.rules.ibs_cbs import cbs_amount, ibs_municipal_amount, ibs_state_amount
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import make_ibs_cbs, make_invoice, make_provider

ALL_RULES = (cbs_amount, ibs_state_amount, ibs_municipal_amount)


def _highlighted(tables, competence: date, **rate_overrides):
    params = tables.ibs_cbs(competence).params
    rates = {
        "cbs_rate": params.cbs_rate,
        "ibs_state_rate": params.ibs_state_rate,
        "ibs_municipal_rate": params.ibs_municipal_rate,
    } | rate_overrides
    return make_invoice(
        competence_date=competence, ibs_cbs=make_ibs_cbs(base=Decimal("1000.00"), **rates)
    )


@pytest.mark.parametrize("competence", [date(2026, 6, 1), date(2027, 6, 1)])
@pytest.mark.parametrize("rule", ALL_RULES)
def test_correct_highlight_is_ok(tables, rule, competence):
    assert rule(_highlighted(tables, competence), tables).status is RuleStatus.OK


def test_wrong_cbs_rate_is_divergent(tables):
    invoice = _highlighted(tables, date(2027, 6, 1), cbs_rate=Decimal("0.05"))
    outcome = cbs_amount(invoice, tables)
    assert outcome.status is RuleStatus.DIVERGENT
    assert "differs from the table" in outcome.detail


def test_2026_rates_applied_to_2027_invoice_is_divergent(tables):
    rates_2026 = tables.ibs_cbs(date(2026, 6, 1)).params
    invoice = _highlighted(tables, date(2027, 6, 1), cbs_rate=rates_2026.cbs_rate)
    assert cbs_amount(invoice, tables).status is RuleStatus.DIVERGENT


def test_missing_group_when_optional_is_not_applicable(tables):
    day = date(2026, 6, 1)
    if tables.ibs_cbs(day).params.mandatory:
        pytest.skip("IBS/CBS is mandatory in this table version")
    invoice = make_invoice(competence_date=day)
    assert cbs_amount(invoice, tables).status is RuleStatus.NOT_APPLICABLE


def test_missing_group_when_mandatory_is_divergent(tables):
    day = date(2027, 6, 1)
    assert tables.ibs_cbs(day).params.mandatory
    invoice = make_invoice(competence_date=day)
    assert cbs_amount(invoice, tables).status is RuleStatus.DIVERGENT


def test_simples_provider_not_applicable(tables):
    invoice = make_invoice(
        competence_date=date(2027, 6, 1),
        provider=make_provider(simples=SimplesNacionalOption.ME_EPP),
    )
    assert cbs_amount(invoice, tables).status is RuleStatus.NOT_APPLICABLE

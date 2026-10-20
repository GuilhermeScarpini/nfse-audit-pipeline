from decimal import Decimal

import pytest
from pydantic import ValidationError

from nfse_audit.domain import IssInfo, IssWithholding, Service


def _iss(**overrides):
    data = {
        "base": "1000.00",
        "rate": "0.05",
        "amount": "50.00",
        "withholding": IssWithholding.NOT_WITHHELD,
    }
    return IssInfo(**(data | overrides))


def test_money_is_quantized_to_cents():
    assert _iss(amount="50").amount == Decimal("50.00")


@pytest.mark.parametrize("bad", [50.0, "-1.00", "50.001"])
def test_money_rejects_float_negative_and_sub_cent(bad):
    with pytest.raises(ValidationError):
        _iss(amount=bad)


@pytest.mark.parametrize("bad", [0.05, "5", "-0.01"])
def test_rate_must_be_a_decimal_fraction(bad):
    with pytest.raises(ValidationError):
        _iss(rate=bad)


def test_invoice_is_immutable(make_invoice):
    invoice = make_invoice()
    with pytest.raises(ValidationError):
        invoice.number = "2"


def test_invoice_rejects_unknown_fields(make_invoice):
    with pytest.raises(ValidationError):
        make_invoice(unexpected="x")


def test_inconsistent_iss_amount_is_accepted_for_the_rule_engine_to_report(make_invoice):
    # 5% of 1000.00 is 50.00; the model must not reject the wrong value
    invoice = make_invoice(
        iss=_iss(amount="40.00"),
    )
    assert invoice.iss.amount == Decimal("40.00")


def test_service_lc116_subitem():
    service = Service(code="010501", description="Software", incidence_municipality_code="3550308")
    assert service.lc116_subitem == "01.05"


def test_provider_simples_flag(make_invoice):
    assert make_invoice().provider.is_simples_nacional is False

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from nfse_audit.domain import (
    Invoice,
    IssInfo,
    IssWithholding,
    Provider,
    Service,
    SimplesNacionalOption,
    Taker,
)
from nfse_audit.domain.cnpj import compute_check_digits


def synthetic_cnpj(seq: int) -> str:
    """Synthetic alphanumeric CNPJ with the "SY" prefix used across the project."""
    base = f"SY{seq:06d}0001"
    return base + compute_check_digits(base)


PROVIDER_CNPJ = synthetic_cnpj(1)
TAKER_CNPJ = synthetic_cnpj(2)


def _invoice_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "access_key": "1" * 50,
        "number": "1",
        "issued_at": datetime(2026, 3, 10, 9, 30),
        "competence_date": date(2026, 3, 1),
        "provider": Provider(
            cnpj=PROVIDER_CNPJ,
            name="Synthetic Provider Ltda",
            municipality_code="3550308",
            simples_nacional=SimplesNacionalOption.NOT_OPTANT,
        ),
        "taker": Taker(cnpj=TAKER_CNPJ, name="Synthetic Taker SA", municipality_code="3550308"),
        "service": Service(
            code="170101",
            description="Consulting",
            incidence_municipality_code="3550308",
        ),
        "service_amount": Decimal("1000.00"),
        "iss": IssInfo(
            base=Decimal("1000.00"),
            rate=Decimal("0.05"),
            amount=Decimal("50.00"),
            withholding=IssWithholding.NOT_WITHHELD,
        ),
    }
    data.update(overrides)
    return data


@pytest.fixture
def make_invoice() -> Callable[..., Invoice]:
    """Build a valid invoice; pass keyword overrides for the fields under test."""

    def factory(**overrides: Any) -> Invoice:
        return Invoice(**_invoice_data(**overrides))

    return factory

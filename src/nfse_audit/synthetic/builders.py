"""Builders of synthetic domain objects, shared by the data generator and the tests.

Every CNPJ starts with "SY" (an alphanumeric CNPJ, valid since July 2026), so
synthetic data is recognizable at a glance and cannot clash with a real numeric CNPJ.
The default invoice is fully compliant for competence 2026-03.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from nfse_audit.domain import (
    FederalWithholdings,
    IbsCbsInfo,
    Invoice,
    IssInfo,
    IssWithholding,
    PisCofinsInfo,
    Provider,
    Service,
    SimplesNacionalOption,
    Taker,
)
from nfse_audit.domain.cnpj import compute_check_digits
from nfse_audit.domain.types import CENT

SYNTHETIC_PREFIX = "SY"
SYNTHETIC_MUNICIPALITY = "9999999"
BRT = timezone(timedelta(hours=-3))


def synthetic_cnpj(seq: int, branch: int = 1) -> str:
    base = f"{SYNTHETIC_PREFIX}{seq:06d}{branch:04d}"
    return base + compute_check_digits(base)


def make_provider(
    seq: int = 1,
    simples: SimplesNacionalOption = SimplesNacionalOption.NOT_OPTANT,
    name: str = "Synthetic Provider Ltda",
) -> Provider:
    return Provider(
        cnpj=synthetic_cnpj(seq),
        name=name,
        municipality_code=SYNTHETIC_MUNICIPALITY,
        simples_nacional=simples,
    )


def make_taker(seq: int = 2, name: str = "Synthetic Taker SA") -> Taker:
    return Taker(cnpj=synthetic_cnpj(seq), name=name, municipality_code=SYNTHETIC_MUNICIPALITY)


def make_service(code: str = "170101", description: str = "Consulting") -> Service:
    return Service(
        code=code, description=description, incidence_municipality_code=SYNTHETIC_MUNICIPALITY
    )


def make_iss(
    base: str | Decimal = "1000.00",
    rate: str | Decimal = "0.05",
    amount: str | Decimal | None = None,
    withholding: IssWithholding = IssWithholding.NOT_WITHHELD,
) -> IssInfo:
    base, rate = Decimal(base), Decimal(rate)
    return IssInfo(
        base=base,
        rate=rate,
        amount=Decimal(amount)
        if amount is not None
        else (base * rate).quantize(CENT, rounding=ROUND_HALF_UP),
        withholding=withholding,
    )


def make_withholdings(**amounts: str | Decimal) -> FederalWithholdings:
    return FederalWithholdings(**{name: Decimal(value) for name, value in amounts.items()})


def make_pis_cofins(pis: str | Decimal, cofins: str | Decimal) -> PisCofinsInfo:
    return PisCofinsInfo(pis_amount=Decimal(pis), cofins_amount=Decimal(cofins))


def make_ibs_cbs(
    base: str | Decimal,
    cbs_rate: str | Decimal,
    ibs_state_rate: str | Decimal,
    ibs_municipal_rate: str | Decimal,
) -> IbsCbsInfo:
    base = Decimal(base)
    rates = [Decimal(r) for r in (cbs_rate, ibs_state_rate, ibs_municipal_rate)]
    cbs, ibs_state, ibs_mun = (
        (base * rate).quantize(CENT, rounding=ROUND_HALF_UP) for rate in rates
    )
    return IbsCbsInfo(
        base=base,
        cbs_rate=rates[0],
        cbs_amount=cbs,
        ibs_state_rate=rates[1],
        ibs_state_amount=ibs_state,
        ibs_municipal_rate=rates[2],
        ibs_municipal_amount=ibs_mun,
    )


def make_invoice(**overrides: Any) -> Invoice:
    """Consulting service (17.01) of R$ 1000.00, compliant for competence 2026-03."""
    data: dict[str, Any] = {
        "access_key": "1" * 50,
        "number": "1",
        "issued_at": datetime(2026, 3, 10, 9, 30, tzinfo=BRT),
        "competence_date": date(2026, 3, 1),
        "provider": make_provider(),
        "taker": make_taker(),
        "service": make_service(),
        "service_amount": Decimal("1000.00"),
        "iss": make_iss(),
        "withholdings": make_withholdings(irrf="15.00", pis="6.50", cofins="30.00", csll="10.00"),
        "pis_cofins": make_pis_cofins(pis="6.50", cofins="30.00"),
    }
    data.update(overrides)
    return Invoice(**data)

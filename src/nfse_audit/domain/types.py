"""Value types shared by the domain models.

Money and rates are Decimal, never float: an audit compares values to the cent,
and float cannot represent 0.10 exactly. Floats are rejected at the boundary
instead of being silently converted.
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, StringConstraints

from nfse_audit.domain.cnpj import normalize_cnpj

CENT = Decimal("0.01")


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("use str, int or Decimal for monetary values, never float")
    return value


def _money(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("monetary value cannot be negative")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError(f"monetary value has more than 2 decimal places: {value}")
    return value.quantize(CENT)


def _rate(value: Decimal) -> Decimal:
    if not Decimal(0) <= value <= Decimal(1):
        raise ValueError(f"rate must be a fraction between 0 and 1, got {value}")
    return value


Money = Annotated[Decimal, BeforeValidator(_reject_float), AfterValidator(_money)]
"""Non-negative amount in BRL with at most 2 decimal places."""

Rate = Annotated[Decimal, BeforeValidator(_reject_float), AfterValidator(_rate)]
"""Tax rate as a fraction: 0.05 means 5%."""

Cnpj = Annotated[str, BeforeValidator(normalize_cnpj)]
"""14-character CNPJ (numeric or alphanumeric), without formatting."""

MunicipalityCode = Annotated[str, StringConstraints(pattern=r"^\d{7}$")]
"""IBGE municipality code (7 digits)."""

ServiceCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]
"""National tax code of the service (cTribNac): LC 116 item, subitem and breakdown."""

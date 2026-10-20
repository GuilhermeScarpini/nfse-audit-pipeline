"""Tax tables versioned by effective date.

A table is a sequence of versions, each valid for a closed date interval. The
version applied to an invoice is the one in force on its competence date, not on
the date it is processed: re-auditing a 2026 invoice in 2030 gives the same result.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nfse_audit.domain.types import Money, Rate


class NoVersionInForce(LookupError):
    """No version of the table covers the requested date."""


class Params(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TableVersion[P: Params](BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_from: date
    valid_to: date | None = None
    legal_basis: str = Field(min_length=1)
    verified: bool
    """False when a value still needs confirmation against the official source."""
    notes: str | None = None
    params: P

    @model_validator(mode="after")
    def _interval_is_ordered(self):
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError(f"valid_to {self.valid_to} is before valid_from {self.valid_from}")
        return self

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)

    @property
    def label(self) -> str:
        return (
            f"{self.valid_from.isoformat()}..{self.valid_to.isoformat() if self.valid_to else ''}"
        )


class TaxTable[P: Params](BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    description: str
    versions: list[TableVersion[P]] = Field(min_length=1)

    @model_validator(mode="after")
    def _versions_are_contiguous(self):
        for previous, current in zip(self.versions, self.versions[1:], strict=False):
            if previous.valid_to is None:
                raise ValueError(f"{self.id}: only the last version may be open-ended")
            if current.valid_from != previous.valid_to + timedelta(days=1):
                raise ValueError(
                    f"{self.id}: version starting {current.valid_from} must start the day after "
                    f"{previous.valid_to} (no gaps or overlaps)"
                )
        return self

    def at(self, day: date) -> TableVersion[P]:
        for version in self.versions:
            if version.covers(day):
                return version
        raise NoVersionInForce(f"table {self.id!r} has no version in force on {day.isoformat()}")


# --- Parameters of each table ---


class IssLimits(Params):
    min_rate: Rate
    max_rate: Rate
    below_min_allowed_subitems: list[str] = []
    """LC 116 subitems that may be taxed below the minimum rate."""


class MunicipalIss(Params):
    municipality_code: str
    municipality_name: str
    synthetic: bool = False
    """True for fictitious municipalities used only to demonstrate versioning."""
    rates: dict[str, Rate]
    """ISS rate per LC 116 subitem ("01.05")."""


class IrrfGroup(Params):
    name: str
    rate: Rate
    subitems: list[str]


class Irrf(Params):
    min_amount: Money
    """Below this amount the withholding is waived."""
    groups: list[IrrfGroup]

    def rate_for(self, subitem: str) -> IrrfGroup | None:
        return next((group for group in self.groups if subitem in group.subitems), None)


WithheldTax = Literal["pis", "cofins", "csll"]


class FederalWithholding(Params):
    rates: dict[WithheldTax, Rate]
    """Taxes withheld in this period. A tax missing from the map is not withheld."""
    subitems: list[str]
    """LC 116 subitems subject to withholding."""
    min_total: Money
    """Withholding is waived when the sum of the withheld taxes is at most this value."""


class IbsCbs(Params):
    cbs_rate: Rate
    ibs_state_rate: Rate
    ibs_municipal_rate: Rate
    mandatory: bool
    """Whether highlighting IBS/CBS on the invoice is mandatory in this period."""

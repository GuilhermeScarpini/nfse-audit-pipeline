"""Domain model of an NFS-e, independent of the XML layout it came from.

Models only reject data that is structurally impossible (malformed CNPJ, negative
amount). Business inconsistencies such as a wrong ISS amount are NOT rejected here:
reporting them is the job of the rule engine.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from nfse_audit.domain.types import Cnpj, Money, MunicipalityCode, Rate, ServiceCode


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SimplesNacionalOption(StrEnum):
    NOT_OPTANT = "not_optant"
    MEI = "mei"
    ME_EPP = "me_epp"


class IssWithholding(StrEnum):
    NOT_WITHHELD = "not_withheld"
    BY_TAKER = "by_taker"
    BY_INTERMEDIARY = "by_intermediary"


class Provider(DomainModel):
    cnpj: Cnpj
    name: str = Field(min_length=1)
    municipality_code: MunicipalityCode
    simples_nacional: SimplesNacionalOption

    @property
    def is_simples_nacional(self) -> bool:
        return self.simples_nacional is not SimplesNacionalOption.NOT_OPTANT


class Taker(DomainModel):
    cnpj: Cnpj
    name: str = Field(min_length=1)
    municipality_code: MunicipalityCode | None = None


class Service(DomainModel):
    code: ServiceCode
    description: str = Field(min_length=1)
    incidence_municipality_code: MunicipalityCode

    @property
    def lc116_subitem(self) -> str:
        """LC 116/2003 subitem, e.g. code "010501" -> "01.05"."""
        return f"{self.code[:2]}.{self.code[2:4]}"


class IssInfo(DomainModel):
    base: Money
    rate: Rate
    amount: Money
    withholding: IssWithholding


class FederalWithholdings(DomainModel):
    """Federal taxes withheld by the taker, as declared on the invoice."""

    irrf: Money = Decimal("0.00")
    csll: Money = Decimal("0.00")
    pis: Money = Decimal("0.00")
    cofins: Money = Decimal("0.00")


class PisCofinsInfo(DomainModel):
    """PIS/COFINS of the operation (vPis/vCofins), withheld or not. Extinct from 2027."""

    pis_amount: Money
    cofins_amount: Money


class IbsCbsInfo(DomainModel):
    """IBS and CBS highlighted on the invoice (tax reform, LC 214/2025)."""

    base: Money
    cbs_rate: Rate
    cbs_amount: Money
    ibs_state_rate: Rate
    ibs_state_amount: Money
    ibs_municipal_rate: Rate
    ibs_municipal_amount: Money

    @property
    def ibs_amount(self) -> Decimal:
        return self.ibs_state_amount + self.ibs_municipal_amount


class Invoice(DomainModel):
    access_key: str = Field(pattern=r"^\d{50}$")
    number: str = Field(min_length=1)
    issued_at: datetime
    competence_date: date
    provider: Provider
    taker: Taker
    service: Service
    service_amount: Money
    iss: IssInfo
    withholdings: FederalWithholdings = FederalWithholdings()
    pis_cofins: PisCofinsInfo | None = None
    ibs_cbs: IbsCbsInfo | None = None

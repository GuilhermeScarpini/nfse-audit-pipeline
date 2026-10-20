"""Loads the YAML tax tables and answers "which version applies on this date?"."""

from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from nfse_audit.tax_tables.models import (
    FederalWithholding,
    IbsCbs,
    Irrf,
    IssLimits,
    MunicipalIss,
    NoVersionInForce,
    TableVersion,
    TaxTable,
)

DEFAULT_TABLES_DIR = Path(str(files("nfse_audit.tax_tables") / "tables"))


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class TaxTables:
    def __init__(
        self,
        iss_limits: TaxTable[IssLimits],
        municipal_iss: dict[str, TaxTable[MunicipalIss]],
        irrf: TaxTable[Irrf],
        federal_withholding: TaxTable[FederalWithholding],
        ibs_cbs: TaxTable[IbsCbs],
    ) -> None:
        self._iss_limits = iss_limits
        self._municipal_iss = municipal_iss
        self._irrf = irrf
        self._federal_withholding = federal_withholding
        self._ibs_cbs = ibs_cbs

    @classmethod
    def from_directory(cls, directory: Path = DEFAULT_TABLES_DIR) -> "TaxTables":
        federal = directory / "federal"
        municipal: dict[str, TaxTable[MunicipalIss]] = {}
        for path in sorted((directory / "municipal").glob("*.yaml")):
            table = TaxTable[MunicipalIss].model_validate(_read(path))
            code = table.versions[0].params.municipality_code
            if any(v.params.municipality_code != code for v in table.versions):
                raise ValueError(f"{path.name}: all versions must refer to municipality {code}")
            municipal[code] = table
        return cls(
            iss_limits=TaxTable[IssLimits].model_validate(_read(federal / "iss_limits.yaml")),
            municipal_iss=municipal,
            irrf=TaxTable[Irrf].model_validate(_read(federal / "irrf.yaml")),
            federal_withholding=TaxTable[FederalWithholding].model_validate(
                _read(federal / "federal_withholding.yaml")
            ),
            ibs_cbs=TaxTable[IbsCbs].model_validate(_read(federal / "ibs_cbs.yaml")),
        )

    def iss_limits(self, day: date) -> TableVersion[IssLimits]:
        return self._iss_limits.at(day)

    def municipal_iss(self, municipality_code: str, day: date) -> TableVersion[MunicipalIss]:
        table = self._municipal_iss.get(municipality_code)
        if table is None:
            raise NoVersionInForce(f"no ISS table for municipality {municipality_code}")
        return table.at(day)

    def irrf(self, day: date) -> TableVersion[Irrf]:
        return self._irrf.at(day)

    def federal_withholding(self, day: date) -> TableVersion[FederalWithholding]:
        return self._federal_withholding.at(day)

    def ibs_cbs(self, day: date) -> TableVersion[IbsCbs]:
        return self._ibs_cbs.at(day)

    @property
    def municipalities(self) -> list[str]:
        return sorted(self._municipal_iss)

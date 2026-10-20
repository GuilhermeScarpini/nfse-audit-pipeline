from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from nfse_audit.tax_tables import NoVersionInForce, TaxTable, TaxTables
from nfse_audit.tax_tables.models import IbsCbs


def _version(valid_from, valid_to=None, cbs="0.009"):
    return {
        "valid_from": valid_from,
        "valid_to": valid_to,
        "legal_basis": "test",
        "verified": True,
        "params": {
            "cbs_rate": cbs,
            "ibs_state_rate": "0",
            "ibs_municipal_rate": "0",
            "mandatory": False,
            "base_deductions": ["iss"],
        },
    }


def _table(*versions):
    return TaxTable[IbsCbs].model_validate(
        {"id": "t", "description": "test", "versions": list(versions)}
    )


@pytest.fixture
def table():
    return _table(
        _version("2026-01-01", "2026-12-31", cbs="0.009"),
        _version("2027-01-01", None, cbs="0.088"),
    )


@pytest.mark.parametrize(
    ("day", "expected_cbs"),
    [
        (date(2026, 1, 1), "0.009"),  # first day of the first version
        (date(2026, 12, 31), "0.009"),  # last day of the first version
        (date(2027, 1, 1), "0.088"),  # first day of the second version
        (date(2040, 6, 1), "0.088"),  # open-ended version
    ],
)
def test_version_is_chosen_by_date(table, day, expected_cbs):
    assert table.at(day).params.cbs_rate == Decimal(expected_cbs)


def test_date_before_coverage_raises(table):
    with pytest.raises(NoVersionInForce):
        table.at(date(2025, 12, 31))


@pytest.mark.parametrize(
    "versions",
    [
        # gap: 2027-01-01 .. 2027-01-31 uncovered
        (_version("2026-01-01", "2026-12-31"), _version("2027-02-01")),
        # overlap: 2026-12-31 covered twice
        (_version("2026-01-01", "2026-12-31"), _version("2026-12-31")),
        # open-ended version that is not the last one
        (_version("2026-01-01"), _version("2027-01-01")),
    ],
)
def test_versions_must_be_contiguous(versions):
    with pytest.raises(ValidationError):
        _table(*versions)


def test_interval_must_be_ordered():
    with pytest.raises(ValidationError):
        _table(_version("2026-12-31", "2026-01-01"))


def test_default_tables_load():
    tables = TaxTables.from_directory()
    assert "9999999" in tables.municipalities
    assert tables.iss_limits(date(2026, 5, 1)).params.max_rate == Decimal("0.05")


def test_synthetic_municipality_demonstrates_rate_change():
    tables = TaxTables.from_directory()
    rate_2026 = tables.municipal_iss("9999999", date(2026, 12, 1)).params.rates["01.05"]
    rate_2027 = tables.municipal_iss("9999999", date(2027, 1, 1)).params.rates["01.05"]
    assert (rate_2026, rate_2027) == (Decimal("0.02"), Decimal("0.025"))


def test_pis_and_cofins_are_not_withheld_from_2027():
    tables = TaxTables.from_directory()
    assert set(tables.federal_withholding(date(2026, 6, 1)).params.rates) == {
        "pis",
        "cofins",
        "csll",
    }
    assert set(tables.federal_withholding(date(2027, 6, 1)).params.rates) == {"csll"}


def test_unknown_municipality_raises():
    with pytest.raises(NoVersionInForce):
        TaxTables.from_directory().municipal_iss("0000000", date(2026, 1, 1))

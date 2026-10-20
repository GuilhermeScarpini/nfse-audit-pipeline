import pytest

from nfse_audit.rules.engine import RuleEngine
from nfse_audit.tax_tables import TaxTables


@pytest.fixture(scope="session")
def tables() -> TaxTables:
    return TaxTables.from_directory()


@pytest.fixture(scope="session")
def engine(tables: TaxTables) -> RuleEngine:
    return RuleEngine(tables)

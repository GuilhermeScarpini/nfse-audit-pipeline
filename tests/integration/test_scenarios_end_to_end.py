"""Generate -> XML -> extract -> audit: each scenario must flag exactly its planted errors."""

import json

import pytest

from nfse_audit.cli import main
from nfse_audit.extraction import ExtractorRegistry
from nfse_audit.extraction.national_xml import NationalXmlExtractor
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.generator import InvoiceFactory, generate, random_invoices, scenarios
from nfse_audit.synthetic.xml_writer import to_nfse_xml

REGISTRY = ExtractorRegistry([NationalXmlExtractor()])


def _audit(engine, invoice):
    return engine.audit(REGISTRY.extract("doc.xml", to_nfse_xml(invoice)))


@pytest.mark.parametrize("index", range(16))
def test_scenario_flags_exactly_the_planted_errors(tables, engine, index):
    scenario = scenarios(InvoiceFactory(tables, seed=42))[index]
    audit = _audit(engine, scenario.invoice)
    divergent = {r.rule_id for r in audit.results if r.status is RuleStatus.DIVERGENT}
    errors = {r.rule_id for r in audit.results if r.status is RuleStatus.ERROR}
    assert (divergent, errors) == (scenario.expected_divergent, scenario.expected_errors), (
        scenario.name
    )


def test_generation_is_deterministic(tables):
    first = [to_nfse_xml(s.invoice) for s in scenarios(InvoiceFactory(tables, seed=1))]
    second = [to_nfse_xml(s.invoice) for s in scenarios(InvoiceFactory(tables, seed=1))]
    assert first == second


def test_random_invoices_are_auditable(tables, engine):
    for invoice in random_invoices(InvoiceFactory(tables, seed=3), 25):
        assert _audit(engine, invoice).results


def test_cli_generate_then_audit(tmp_path, tables, capsys):
    data, reports = tmp_path / "data", tmp_path / "reports"
    assert main(["generate", "--out", str(data), "--random", "5"]) == 0
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["scenarios"]) == 16

    assert main(["audit", str(data), "--out", str(reports)]) == 0
    report = json.loads(next(reports.glob("*.json")).read_text(encoding="utf-8"))
    assert report["summary"]["invoices_audited"] == 16 + 5
    assert {e["source"] for e in report["errors"]} == {"broken.xml", "xxe-attempt.xml"}
    assert next(reports.glob("*.xlsx")).stat().st_size > 0


def test_cli_validate(tmp_path, tables):
    generate(tmp_path, tables, extra=0)
    valid = sorted(tmp_path.glob("0*.xml"))
    assert main(["validate", *map(str, valid)]) == 0
    assert main(["validate", str(tmp_path / "broken.xml")]) == 1

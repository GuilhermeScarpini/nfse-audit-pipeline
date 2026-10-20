from datetime import date

from nfse_audit.rules.base import Outcome, rule
from nfse_audit.rules.engine import DEFAULT_RULES, RuleEngine
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import make_invoice, make_iss


def test_compliant_invoice_has_no_divergence(engine):
    audit = engine.audit(make_invoice())
    assert audit.status is RuleStatus.OK
    assert len(audit.results) == len(DEFAULT_RULES)


def test_divergent_rule_marks_the_invoice_divergent(engine):
    audit = engine.audit(make_invoice(iss=make_iss(amount="40.00")))
    assert audit.status is RuleStatus.DIVERGENT
    divergent = [r.rule_id for r in audit.results if r.status is RuleStatus.DIVERGENT]
    assert divergent == ["ISS_AMOUNT"]


def test_result_records_the_table_version_used(engine):
    audit = engine.audit(make_invoice(competence_date=date(2027, 2, 1)))
    municipal = next(r for r in audit.results if r.rule_id == "ISS_RATE_MUNICIPAL")
    assert municipal.table_version == "2027-01-01.."
    assert municipal.table_verified is True


def test_competence_outside_table_coverage_is_an_error(engine):
    audit = engine.audit(make_invoice(competence_date=date(2025, 12, 1)))
    assert audit.status is RuleStatus.ERROR


def test_a_crashing_rule_does_not_stop_the_others(tables):
    @rule("BOOM", "always fails")
    def boom(invoice, tables):
        raise RuntimeError("bug")

    @rule("FINE", "always ok")
    def fine(invoice, tables):
        return Outcome(RuleStatus.OK)

    audit = RuleEngine(tables, rules=[boom, fine]).audit(make_invoice())
    assert [r.status for r in audit.results] == [RuleStatus.ERROR, RuleStatus.OK]

import logging
from collections.abc import Sequence

from nfse_audit.domain import Invoice
from nfse_audit.rules import federal_withholding, ibs_cbs, irrf, iss
from nfse_audit.rules.base import Outcome, Rule
from nfse_audit.rules.results import InvoiceAudit, RuleResult, RuleStatus
from nfse_audit.tax_tables import NoVersionInForce, TaxTables

logger = logging.getLogger(__name__)

DEFAULT_RULES: tuple[Rule, ...] = (
    *iss.RULES,
    *irrf.RULES,
    *federal_withholding.RULES,
    *ibs_cbs.RULES,
)


class RuleEngine:
    def __init__(self, tables: TaxTables, rules: Sequence[Rule] = DEFAULT_RULES) -> None:
        self._tables = tables
        self._rules = tuple(rules)

    def audit(self, invoice: Invoice) -> InvoiceAudit:
        return InvoiceAudit(
            access_key=invoice.access_key,
            number=invoice.number,
            competence_date=invoice.competence_date,
            provider_cnpj=invoice.provider.cnpj,
            taker_cnpj=invoice.taker.cnpj,
            service_amount=invoice.service_amount,
            results=[self._run(rule, invoice) for rule in self._rules],
        )

    def _run(self, rule: Rule, invoice: Invoice) -> RuleResult:
        try:
            outcome = rule(invoice, self._tables)
        except NoVersionInForce as exc:
            outcome = Outcome(RuleStatus.ERROR, detail=str(exc))
        except Exception as exc:
            # One broken rule must not hide the results of the others.
            logger.exception("rule %s failed on invoice %s", rule.id, invoice.access_key)
            outcome = Outcome(RuleStatus.ERROR, detail=f"unexpected error: {exc}")
        table = outcome.table
        return RuleResult(
            rule_id=rule.id,
            description=rule.description,
            status=outcome.status,
            expected=outcome.expected,
            found=outcome.found,
            detail=outcome.detail,
            legal_basis=outcome.legal_basis,
            table_id=outcome.table_id,
            table_version=table.label if table else None,
            table_verified=table.verified if table else None,
        )

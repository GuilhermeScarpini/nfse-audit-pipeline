from nfse_audit.domain import Invoice
from nfse_audit.extraction import ExtractionError, ExtractorRegistry
from nfse_audit.pipeline import audit_documents
from nfse_audit.rules.results import RuleStatus
from nfse_audit.synthetic.builders import make_invoice, make_iss


class FakeExtractor:
    """Test double: maps document content to prebuilt invoices."""

    name = "fake"

    def __init__(self, invoices: dict[bytes, Invoice]) -> None:
        self._invoices = invoices

    def supports(self, filename: str, content: bytes) -> bool:
        return filename.endswith(".fake")

    def extract(self, content: bytes) -> Invoice:
        if content not in self._invoices:
            raise ExtractionError("unreadable")
        return self._invoices[content]


def _registry() -> ExtractorRegistry:
    return ExtractorRegistry(
        [
            FakeExtractor(
                {
                    b"ok": make_invoice(),
                    b"bad-iss": make_invoice(access_key="2" * 50, iss=make_iss(amount="1.00")),
                    b"same-key": make_invoice(number="99"),
                }
            )
        ]
    )


def test_pipeline_audits_and_collects_errors(engine):
    report = audit_documents(
        "b1",
        [
            ("a.fake", b"ok"),
            ("b.fake", b"bad-iss"),
            ("c.fake", b"garbage"),
            ("d.pdf", b"%PDF"),
        ],
        _registry(),
        engine,
    )
    assert [a.status for a in report.invoices] == [RuleStatus.OK, RuleStatus.DIVERGENT]
    assert {e.source: e.message for e in report.errors} == {
        "c.fake": "unreadable",
        "d.pdf": "unsupported document format: d.pdf",
    }


def test_duplicate_content_and_duplicate_invoice_are_reported(engine):
    report = audit_documents(
        "b1",
        [("a.fake", b"ok"), ("copy.fake", b"ok"), ("other.fake", b"same-key")],
        _registry(),
        engine,
    )
    assert len(report.invoices) == 1
    messages = {e.source: e.message for e in report.errors}
    assert messages["copy.fake"] == "duplicate of a.fake"
    assert "already audited from a.fake" in messages["other.fake"]

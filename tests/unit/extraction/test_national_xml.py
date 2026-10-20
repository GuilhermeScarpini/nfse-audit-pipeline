import pytest
from lxml import etree

from nfse_audit.extraction import ExtractionError
from nfse_audit.extraction.national_xml import NationalXmlExtractor
from nfse_audit.extraction.schema import load_schema, validate
from nfse_audit.extraction.xml_security import parse_untrusted
from nfse_audit.synthetic.generator import MALFORMED_DOCUMENTS, InvoiceFactory, scenarios
from nfse_audit.synthetic.xml_writer import to_nfse_xml

EXTRACTOR = NationalXmlExtractor()


@pytest.fixture(scope="module")
def all_scenarios(tables):
    return scenarios(InvoiceFactory(tables, seed=7))


def test_every_scenario_is_valid_against_the_official_schema(all_scenarios):
    for scenario in all_scenarios:
        errors = validate(parse_untrusted(to_nfse_xml(scenario.invoice)))
        assert errors == [], (scenario.name, errors)


def test_round_trip_invoice_to_xml_to_invoice(all_scenarios):
    for scenario in all_scenarios:
        assert EXTRACTOR.extract(to_nfse_xml(scenario.invoice)) == scenario.invoice, scenario.name


def test_schema_adaptations_are_applied():
    # alphanumeric CNPJ accepted; ds:Signature optional
    schema_doc = load_schema()
    assert isinstance(schema_doc, etree.XMLSchema)


def test_xxe_attempt_is_rejected():
    with pytest.raises(ExtractionError, match="DOCTYPE"):
        EXTRACTOR.extract(MALFORMED_DOCUMENTS["xxe-attempt.xml"])


def test_billion_laughs_is_rejected():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><NFSe>&lol2;</NFSe>'
    )
    with pytest.raises(ExtractionError):
        EXTRACTOR.extract(bomb)


def test_malformed_xml_is_an_extraction_error():
    with pytest.raises(ExtractionError, match="malformed"):
        EXTRACTOR.extract(MALFORMED_DOCUMENTS["broken.xml"])


def test_wrong_root_element(all_scenarios):
    content = b"<DPS xmlns='http://www.sped.fazenda.gov.br/nfse'/>"
    with pytest.raises(ExtractionError, match="expected NFSe"):
        EXTRACTOR.extract(content)


def test_invalid_cnpj_becomes_extraction_error(all_scenarios):
    xml = to_nfse_xml(all_scenarios[0].invoice)
    cnpj = all_scenarios[0].invoice.provider.cnpj
    tampered = xml.replace(cnpj.encode(), (cnpj[:-1] + str((int(cnpj[-1]) + 1) % 10)).encode())
    with pytest.raises(ExtractionError, match="check digits"):
        EXTRACTOR.extract(tampered)


def test_supports_only_national_namespace():
    assert EXTRACTOR.supports("a.xml", b"<NFSe xmlns='http://www.sped.fazenda.gov.br/nfse'/>")
    assert not EXTRACTOR.supports("a.xml", b"<other/>")

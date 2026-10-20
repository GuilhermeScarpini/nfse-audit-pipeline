"""XSD validation against the official NFS-e schemas, with documented adaptations.

See schemas/v1.01/SOURCE.md for provenance and the reason for each adaptation.
"""

import shutil
import tempfile
from functools import cache
from importlib.resources import files
from pathlib import Path

from lxml import etree

SCHEMA_DIR = Path(str(files("nfse_audit.extraction") / "schemas" / "v1.01"))
XS = "{http://www.w3.org/2001/XMLSchema}"

ALPHANUMERIC_CNPJ = "[0-9A-Z]{12}[0-9]{2}"


def _patch_cnpj(tree: etree._ElementTree) -> None:
    pattern = tree.find(f"{XS}simpleType[@name='TSCNPJ']/{XS}restriction/{XS}pattern")
    if pattern is None:
        raise RuntimeError("TSCNPJ pattern not found: schema layout changed")
    pattern.set("value", ALPHANUMERIC_CNPJ)


def _patch_optional_signature(tree: etree._ElementTree) -> None:
    signature = tree.find(
        f"{XS}complexType[@name='TCNFSe']/{XS}sequence/{XS}element[@ref='ds:Signature']"
    )
    if signature is None:
        raise RuntimeError("TCNFSe signature not found: schema layout changed")
    signature.set("minOccurs", "0")


def _patch_serie_anchors(tree: etree._ElementTree) -> None:
    # XSD patterns are implicitly anchored and "^"/"$" are literal characters in XSD
    # regex, so "^0{0,4}\d{1,5}$" rejects every real series in a conforming validator.
    pattern = tree.find(f"{XS}simpleType[@name='TSSerieDPS']/{XS}restriction/{XS}pattern")
    if pattern is None:
        raise RuntimeError("TSSerieDPS pattern not found: schema layout changed")
    pattern.set("value", pattern.get("value", "").removeprefix("^").removesuffix("$"))


PATCHES = {
    "tiposSimples_v1.01.xsd": (_patch_cnpj, _patch_serie_anchors),
    "tiposComplexos_v1.01.xsd": (_patch_optional_signature,),
}


@cache
def load_schema() -> etree.XMLSchema:
    # The schema files are trusted local files (xmldsig uses internal DTD entities),
    # so this parser differs from the hardened one used for untrusted documents.
    parser = etree.XMLParser(resolve_entities=True, no_network=True, load_dtd=False)
    workdir = Path(tempfile.mkdtemp(prefix="nfse-xsd-"))
    for source in SCHEMA_DIR.glob("*.xsd"):
        target = workdir / source.name
        if patches := PATCHES.get(source.name):
            tree = etree.parse(str(source), parser)
            for patch in patches:
                patch(tree)
            tree.write(str(target), xml_declaration=True, encoding="UTF-8")
        else:
            shutil.copy(source, target)
    return etree.XMLSchema(etree.parse(str(workdir / "NFSe_v1.01.xsd"), parser))


def validate(document: etree._Element) -> list[str]:
    """Return schema violations; an empty list means the document is valid."""
    schema = load_schema()
    if schema.validate(document):
        return []
    return [f"line {error.line}: {error.message}" for error in schema.error_log]

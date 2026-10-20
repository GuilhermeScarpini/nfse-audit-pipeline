"""Hardened XML parsing for documents received from outside.

Two classic attacks are blocked:
- XXE (XML External Entity): <!ENTITY x SYSTEM "file:///etc/passwd"> makes a naive
  parser read local files or call URLs and put the content in the document.
- Billion laughs: nested entities that expand a 1 KB file into gigabytes of memory.
Both need a DOCTYPE. An NFS-e never has one, so any DOCTYPE is rejected outright.
"""

from lxml import etree

from nfse_audit.extraction.base import ExtractionError

_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    dtd_validation=False,
    huge_tree=False,
    remove_comments=True,
)


def parse_untrusted(content: bytes) -> etree._Element:
    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise ExtractionError("DOCTYPE/ENTITY declarations are not allowed")
    try:
        root = etree.fromstring(content, _PARSER)
    except etree.XMLSyntaxError as exc:
        raise ExtractionError(f"malformed XML: {exc}") from None
    if root.getroottree().docinfo.doctype:
        raise ExtractionError("DOCTYPE declarations are not allowed")
    return root

"""Serializes a synthetic Invoice as an NFS-e XML in the national layout v1.01.

Synthetic documents are marked as such: tpAmb=2 (test environment), no digital
signature, "SY" CNPJs and verAplic "nfse-audit-synthetic". Fields the domain does
not model (addresses, cIndOp...) get schema-valid placeholder values.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from lxml import etree

from nfse_audit.domain import Invoice, IssWithholding, SimplesNacionalOption
from nfse_audit.domain.types import CENT
from nfse_audit.extraction.national_xml import NS
from nfse_audit.synthetic.builders import BRT

VERSION = "1.01"
APP_VERSION = "nfse-audit-synthetic"


@dataclass(frozen=True)
class Place:
    code: str
    name: str
    uf: str
    cep: str


PLACES = {
    "9999999": Place("9999999", "Municipio Sintetico", "SP", "00000000"),
    "3550308": Place("3550308", "Sao Paulo", "SP", "01001000"),
}

SIMPLES_CODE = {
    SimplesNacionalOption.NOT_OPTANT: "1",
    SimplesNacionalOption.MEI: "2",
    SimplesNacionalOption.ME_EPP: "3",
}
ISS_WITHHOLDING_CODE = {
    IssWithholding.NOT_WITHHELD: "1",
    IssWithholding.BY_TAKER: "2",
    IssWithholding.BY_INTERMEDIARY: "3",
}
# (PIS withheld, COFINS withheld, CSLL withheld) -> tpRetPisCofins
PIS_COFINS_CODE = {
    (False, False, False): "0",
    (True, True, True): "3",
    (True, True, False): "4",
    (True, False, False): "5",
    (False, True, False): "6",
    (False, True, True): "7",
    (False, False, True): "8",
    (True, False, True): "9",
}


def _digits(cnpj: str) -> str:
    """14 digits for numeric-only fields (access key) from a possibly alphanumeric CNPJ."""
    return "".join(str((ord(char) - 48) % 10) for char in cnpj)


def _mod11(digits: str) -> str:
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(d) * weights[i % 8] for i, d in enumerate(reversed(digits)))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def synthetic_access_key(municipality: str, cnpj: str, number: int, competence: date) -> str:
    """50 digits with the official structure; the check digit is illustrative."""
    salt = hashlib.sha256(f"{cnpj}{number}".encode()).hexdigest()
    random_code = str(int(salt[:12], 16))[-9:].zfill(9)
    body = f"{municipality}22{_digits(cnpj)}{number:013d}{competence:%y%m}{random_code}"
    return body + _mod11(body)


def _pct(rate: Decimal) -> str:
    return str((rate * 100).quantize(CENT))


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    element = etree.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        element.text = text
    return element


def _datetime(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=BRT)
    return aware.isoformat(timespec="seconds")


def to_nfse_xml(invoice: Invoice, processed_at: datetime | None = None) -> bytes:
    place = PLACES[invoice.service.incidence_municipality_code]
    provider_place = PLACES[invoice.provider.municipality_code]
    processed = processed_at or invoice.issued_at + timedelta(minutes=1)
    is_mei = invoice.provider.simples_nacional is SimplesNacionalOption.MEI

    root = etree.Element(f"{{{NS}}}NFSe", nsmap={None: NS}, versao=VERSION)
    inf = _sub(root, "infNFSe")
    inf.set("Id", f"NFS{invoice.access_key}")
    _sub(inf, "xLocEmi", provider_place.name)
    _sub(inf, "xLocPrestacao", place.name)
    _sub(inf, "nNFSe", invoice.number)
    _sub(inf, "cLocIncid", place.code)
    _sub(inf, "xLocIncid", place.name)
    _sub(inf, "xTribNac", invoice.service.description)
    _sub(inf, "verAplic", APP_VERSION)
    _sub(inf, "ambGer", "2")
    _sub(inf, "tpEmis", "1")
    _sub(inf, "cStat", "100")
    _sub(inf, "dhProc", _datetime(processed))
    _sub(inf, "nDFSe", invoice.number)

    emit = _sub(inf, "emit")
    _sub(emit, "CNPJ", invoice.provider.cnpj)
    _sub(emit, "xNome", invoice.provider.name)
    address = _sub(emit, "enderNac")
    for tag, text in (
        ("xLgr", "Rua Sintetica"),
        ("nro", "1"),
        ("xBairro", "Centro"),
        ("cMun", provider_place.code),
        ("UF", provider_place.uf),
        ("CEP", provider_place.cep),
    ):
        _sub(address, tag, text)

    w = invoice.withholdings
    iss_withheld = (
        invoice.iss.amount
        if invoice.iss.withholding is not IssWithholding.NOT_WITHHELD
        else Decimal(0)
    )
    total_withheld = w.irrf + w.csll + w.pis + w.cofins + iss_withheld
    values = _sub(inf, "valores")
    if not is_mei:
        _sub(values, "vBC", _money(invoice.iss.base))
        _sub(values, "pAliqAplic", _pct(invoice.iss.rate))
        _sub(values, "vISSQN", _money(invoice.iss.amount))
    _sub(values, "vTotalRet", _money(total_withheld))
    _sub(values, "vLiq", _money(invoice.service_amount - total_withheld))

    if invoice.ibs_cbs is not None:
        _ibs_cbs_nfse(inf, invoice, place)

    dps = _sub(inf, "DPS")
    dps.set("versao", VERSION)
    _dps(dps, invoice, place, is_mei)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _ibs_cbs_nfse(inf: etree._Element, invoice: Invoice, place: Place) -> None:
    info = invoice.ibs_cbs
    assert info is not None
    group = _sub(inf, "IBSCBS")
    _sub(group, "cLocalidadeIncid", place.code)
    _sub(group, "xLocalidadeIncid", place.name)
    values = _sub(group, "valores")
    _sub(values, "vBC", _money(info.base))
    for tag, nominal, effective, rate in (
        ("uf", "pIBSUF", "pAliqEfetUF", info.ibs_state_rate),
        ("mun", "pIBSMun", "pAliqEfetMun", info.ibs_municipal_rate),
        ("fed", "pCBS", "pAliqEfetCBS", info.cbs_rate),
    ):
        level = _sub(values, tag)
        _sub(level, nominal, _pct(rate))
        _sub(level, effective, _pct(rate))
    totals = _sub(group, "totCIBS")
    _sub(totals, "vTotNF", _money(invoice.service_amount))
    ibs = _sub(totals, "gIBS")
    _sub(ibs, "vIBSTot", _money(info.ibs_amount))
    _sub(_sub(ibs, "gIBSUFTot"), "vIBSUF", _money(info.ibs_state_amount))
    _sub(_sub(ibs, "gIBSMunTot"), "vIBSMun", _money(info.ibs_municipal_amount))
    _sub(_sub(totals, "gCBS"), "vCBS", _money(info.cbs_amount))


def _dps(dps: etree._Element, invoice: Invoice, place: Place, is_mei: bool) -> None:
    provider_cnpj = invoice.provider.cnpj
    number = int(invoice.number)
    inf = _sub(dps, "infDPS")
    inf.set(
        "Id",
        f"DPS{invoice.provider.municipality_code}2{_digits(provider_cnpj)}{1:05d}{number:015d}",
    )
    _sub(inf, "tpAmb", "2")  # test environment: synthetic data, never production
    _sub(inf, "dhEmi", _datetime(invoice.issued_at))
    _sub(inf, "verAplic", APP_VERSION)
    _sub(inf, "serie", "1")
    _sub(inf, "nDPS", invoice.number)
    _sub(inf, "dCompet", invoice.competence_date.isoformat())
    _sub(inf, "tpEmit", "1")
    _sub(inf, "cLocEmi", invoice.provider.municipality_code)

    prest = _sub(inf, "prest")
    _sub(prest, "CNPJ", provider_cnpj)
    _sub(prest, "xNome", invoice.provider.name)
    reg = _sub(prest, "regTrib")
    _sub(reg, "opSimpNac", SIMPLES_CODE[invoice.provider.simples_nacional])
    if invoice.provider.is_simples_nacional:
        _sub(reg, "regApTribSN", "1")
    _sub(reg, "regEspTrib", "0")

    taker = invoice.taker
    toma = _sub(inf, "toma")
    _sub(toma, "CNPJ", taker.cnpj)
    _sub(toma, "xNome", taker.name)
    if taker.municipality_code:
        taker_place = PLACES[taker.municipality_code]
        end = _sub(toma, "end")
        nac = _sub(end, "endNac")
        _sub(nac, "cMun", taker_place.code)
        _sub(nac, "CEP", taker_place.cep)
        for tag, text in (("xLgr", "Avenida Sintetica"), ("nro", "100"), ("xBairro", "Centro")):
            _sub(end, tag, text)

    serv = _sub(inf, "serv")
    _sub(_sub(serv, "locPrest"), "cLocPrestacao", place.code)
    cserv = _sub(serv, "cServ")
    _sub(cserv, "cTribNac", invoice.service.code)
    _sub(cserv, "xDescServ", invoice.service.description)

    values = _sub(inf, "valores")
    _sub(_sub(values, "vServPrest"), "vServ", _money(invoice.service_amount))
    trib = _sub(values, "trib")
    mun = _sub(trib, "tribMun")
    _sub(mun, "tribISSQN", "1")
    _sub(mun, "tpRetISSQN", ISS_WITHHOLDING_CODE[invoice.iss.withholding])
    if not is_mei:
        _sub(mun, "pAliq", _pct(invoice.iss.rate))
    _federal(trib, invoice)
    _sub(_sub(trib, "totTrib"), "indTotTrib", "0")

    if invoice.ibs_cbs is not None:
        group = _sub(inf, "IBSCBS")
        _sub(group, "finNFSe", "0")
        _sub(group, "cIndOp", "000000")  # schema-valid placeholder (Anexo VII not modeled)
        _sub(group, "indDest", "0")
        sit = _sub(_sub(_sub(group, "valores"), "trib"), "gIBSCBS")
        _sub(sit, "CST", "000")
        _sub(sit, "cClassTrib", "000001")


def _federal(trib: etree._Element, invoice: Invoice) -> None:
    w, pc = invoice.withholdings, invoice.pis_cofins
    if pc is None and (w.pis or w.cofins):
        raise ValueError("withheld PIS/COFINS needs the pis_cofins group (vPis/vCofins)")
    if pc is None and not (w.irrf or w.csll):
        return
    fed = _sub(trib, "tribFed")
    if pc is not None:
        group = _sub(fed, "piscofins")
        _sub(group, "CST", "01")
        _sub(group, "vBCPisCofins", _money(invoice.service_amount))
        if invoice.service_amount:
            _sub(group, "pAliqPis", _pct(pc.pis_amount / invoice.service_amount))
            _sub(group, "pAliqCofins", _pct(pc.cofins_amount / invoice.service_amount))
        _sub(group, "vPis", _money(pc.pis_amount))
        _sub(group, "vCofins", _money(pc.cofins_amount))
        _sub(group, "tpRetPisCofins", PIS_COFINS_CODE[(w.pis > 0, w.cofins > 0, w.csll > 0)])
    if w.irrf:
        _sub(fed, "vRetIRRF", _money(w.irrf))
    if w.csll:
        _sub(fed, "vRetCSLL", _money(w.csll))

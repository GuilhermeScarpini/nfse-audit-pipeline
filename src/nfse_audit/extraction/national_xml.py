"""Extractor for the national NFS-e XML layout (Sistema Nacional NFS-e, v1.00/v1.01).

Percentages in the XML are percent values ("2.00" = 2%); the domain uses fractions.
Paths are relative to NFSe/infNFSe; the DPS part is NFSe/infNFSe/DPS/infDPS.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from lxml import etree
from pydantic import ValidationError

from nfse_audit.domain import (
    FederalWithholdings,
    IbsCbsInfo,
    Invoice,
    IssInfo,
    IssWithholding,
    PisCofinsInfo,
    Provider,
    Service,
    SimplesNacionalOption,
    Taker,
)
from nfse_audit.extraction.base import ExtractionError
from nfse_audit.extraction.xml_security import parse_untrusted

NS = "http://www.sped.fazenda.gov.br/nfse"
_NSMAP = {"n": NS}

SIMPLES_CODES = {
    "1": SimplesNacionalOption.NOT_OPTANT,
    "2": SimplesNacionalOption.MEI,
    "3": SimplesNacionalOption.ME_EPP,
}
ISS_WITHHOLDING_CODES = {
    "1": IssWithholding.NOT_WITHHELD,
    "2": IssWithholding.BY_TAKER,
    "3": IssWithholding.BY_INTERMEDIARY,
}
# tpRetPisCofins -> (PIS withheld, COFINS withheld). CSLL comes from vRetCSLL.
PIS_COFINS_WITHHELD = {
    "0": (False, False),
    "1": (True, True),
    "2": (False, False),
    "3": (True, True),
    "4": (True, True),
    "5": (True, False),
    "6": (False, True),
    "7": (False, True),
    "8": (False, False),
    "9": (True, False),
}
ZERO = Decimal("0.00")


class _Reader:
    def __init__(self, root: etree._Element) -> None:
        self._root = root

    def node(self, path: str) -> etree._Element | None:
        found = self._root.xpath(path, namespaces=_NSMAP)
        return found[0] if found else None

    def text(self, path: str) -> str | None:
        node = self.node(path)
        return node.text.strip() if node is not None and node.text else None

    def required(self, path: str) -> str:
        value = self.text(path)
        if value is None:
            raise ExtractionError(f"missing required element {path}")
        return value

    def decimal(self, path: str, default: Decimal | None = None) -> Decimal | None:
        value = self.text(path)
        if value is None:
            return default
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ExtractionError(f"{path}: not a number: {value!r}") from None

    def money(self, path: str) -> Decimal:
        return self.decimal(path, ZERO) or ZERO

    def rate(self, path: str) -> Decimal | None:
        percent = self.decimal(path)
        return None if percent is None else percent / 100


class NationalXmlExtractor:
    name = "nfse-national-xml"

    def supports(self, filename: str, content: bytes) -> bool:
        return NS.encode() in content[:4096]

    def extract(self, content: bytes) -> Invoice:
        root = parse_untrusted(content)
        if root.tag != f"{{{NS}}}NFSe":
            raise ExtractionError(f"root element is {root.tag}, expected NFSe")
        try:
            return self._invoice(_Reader(root))
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
            )
            raise ExtractionError(f"invalid invoice data: {problems}") from None

    def _invoice(self, r: _Reader) -> Invoice:
        inf = "n:infNFSe"
        dps = f"{inf}/n:DPS/n:infDPS"
        access_id = r.node(inf)
        access_key = (access_id.get("Id") or "") if access_id is not None else ""
        if not access_key.startswith("NFS"):
            raise ExtractionError("infNFSe/@Id must start with NFS")

        service_amount = r.money(f"{dps}/n:valores/n:vServPrest/n:vServ")
        return Invoice(
            access_key=access_key[3:],
            number=r.required(f"{inf}/n:nNFSe"),
            issued_at=datetime.fromisoformat(r.required(f"{dps}/n:dhEmi")),
            competence_date=date.fromisoformat(r.required(f"{dps}/n:dCompet")),
            provider=self._provider(r, inf, dps),
            taker=self._taker(r, dps),
            service=Service(
                code=r.required(f"{dps}/n:serv/n:cServ/n:cTribNac"),
                description=r.required(f"{dps}/n:serv/n:cServ/n:xDescServ"),
                incidence_municipality_code=r.text(f"{inf}/n:cLocIncid")
                or r.required(f"{dps}/n:serv/n:locPrest/n:cLocPrestacao"),
            ),
            service_amount=service_amount,
            iss=self._iss(r, inf, dps, service_amount),
            withholdings=self._withholdings(r, dps),
            pis_cofins=self._pis_cofins(r, dps),
            ibs_cbs=self._ibs_cbs(r, inf),
        )

    def _provider(self, r: _Reader, inf: str, dps: str) -> Provider:
        cnpj = r.text(f"{dps}/n:prest/n:CNPJ")
        if cnpj is None:
            raise ExtractionError("provider without CNPJ is not supported")
        option = r.required(f"{dps}/n:prest/n:regTrib/n:opSimpNac")
        if option not in SIMPLES_CODES:
            raise ExtractionError(f"unknown opSimpNac code {option!r}")
        return Provider(
            cnpj=cnpj,
            name=r.text(f"{dps}/n:prest/n:xNome") or r.required(f"{inf}/n:emit/n:xNome"),
            municipality_code=r.required(f"{inf}/n:emit/n:enderNac/n:cMun"),
            simples_nacional=SIMPLES_CODES[option],
        )

    def _taker(self, r: _Reader, dps: str) -> Taker:
        cnpj = r.text(f"{dps}/n:toma/n:CNPJ")
        if cnpj is None:
            raise ExtractionError(
                "taker without CNPJ is not supported (withholdings need a legal entity)"
            )
        return Taker(
            cnpj=cnpj,
            name=r.required(f"{dps}/n:toma/n:xNome"),
            municipality_code=r.text(f"{dps}/n:toma/n:end/n:endNac/n:cMun"),
        )

    def _iss(self, r: _Reader, inf: str, dps: str, service_amount: Decimal) -> IssInfo:
        trib = f"{dps}/n:valores/n:trib/n:tribMun"
        code = r.required(f"{trib}/n:tpRetISSQN")
        if code not in ISS_WITHHOLDING_CODES:
            raise ExtractionError(f"unknown tpRetISSQN code {code!r}")
        rate = r.rate(f"{inf}/n:valores/n:pAliqAplic") or r.rate(f"{trib}/n:pAliq") or Decimal(0)
        return IssInfo(
            base=r.decimal(f"{inf}/n:valores/n:vBC", service_amount),
            rate=rate,
            amount=r.money(f"{inf}/n:valores/n:vISSQN"),
            withholding=ISS_WITHHOLDING_CODES[code],
        )

    def _withholdings(self, r: _Reader, dps: str) -> FederalWithholdings:
        fed = f"{dps}/n:valores/n:trib/n:tribFed"
        code = r.text(f"{fed}/n:piscofins/n:tpRetPisCofins") or "0"
        if code not in PIS_COFINS_WITHHELD:
            raise ExtractionError(f"unknown tpRetPisCofins code {code!r}")
        pis_withheld, cofins_withheld = PIS_COFINS_WITHHELD[code]
        return FederalWithholdings(
            irrf=r.money(f"{fed}/n:vRetIRRF"),
            csll=r.money(f"{fed}/n:vRetCSLL"),
            pis=r.money(f"{fed}/n:piscofins/n:vPis") if pis_withheld else ZERO,
            cofins=r.money(f"{fed}/n:piscofins/n:vCofins") if cofins_withheld else ZERO,
        )

    def _pis_cofins(self, r: _Reader, dps: str) -> PisCofinsInfo | None:
        group = f"{dps}/n:valores/n:trib/n:tribFed/n:piscofins"
        if r.node(group) is None:
            return None
        return PisCofinsInfo(
            pis_amount=r.money(f"{group}/n:vPis"), cofins_amount=r.money(f"{group}/n:vCofins")
        )

    def _ibs_cbs(self, r: _Reader, inf: str) -> IbsCbsInfo | None:
        group = f"{inf}/n:IBSCBS"
        if r.node(group) is None:
            return None
        values, totals = f"{group}/n:valores", f"{group}/n:totCIBS"
        # Effective rates: the amounts are computed with them (equal to the nominal
        # rates when there is no reduction).
        return IbsCbsInfo(
            base=r.money(f"{values}/n:vBC"),
            cbs_rate=r.rate(f"{values}/n:fed/n:pAliqEfetCBS") or Decimal(0),
            cbs_amount=r.money(f"{totals}/n:gCBS/n:vCBS"),
            ibs_state_rate=r.rate(f"{values}/n:uf/n:pAliqEfetUF") or Decimal(0),
            ibs_state_amount=r.money(f"{totals}/n:gIBS/n:gIBSUFTot/n:vIBSUF"),
            ibs_municipal_rate=r.rate(f"{values}/n:mun/n:pAliqEfetMun") or Decimal(0),
            ibs_municipal_amount=r.money(f"{totals}/n:gIBS/n:gIBSMunTot/n:vIBSMun"),
        )

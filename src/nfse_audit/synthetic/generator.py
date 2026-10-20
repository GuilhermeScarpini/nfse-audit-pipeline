"""Synthetic NFS-e generator: compliant invoices plus scenarios with deliberate errors.

Deterministic: the same seed always produces the same files. Each scenario states
which rules must report a divergence. Those expectations are written by hand on
purpose: the factory computes "correct" values with the same tables the rules use,
so comparing the two alone would not catch a shared bug (the test oracle problem).
"""

import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from nfse_audit.domain import Invoice, SimplesNacionalOption
from nfse_audit.rules.base import ZERO, to_cents
from nfse_audit.synthetic.builders import (
    BRT,
    SYNTHETIC_MUNICIPALITY,
    make_ibs_cbs,
    make_invoice,
    make_iss,
    make_pis_cofins,
    make_provider,
    make_service,
    make_taker,
    make_withholdings,
)
from nfse_audit.synthetic.xml_writer import synthetic_access_key, to_nfse_xml
from nfse_audit.tax_tables import TaxTables

SAO_PAULO = "3550308"
ILLUSTRATIVE_CBS_2027 = Decimal("0.088")
"""Placeholder written on synthetic 2027 invoices while the Senate rate is pending.
The CBS rule reports an error for 2027 regardless of this value."""

NAMES = ("Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel")
SERVICES = {
    "170101": "Consultoria empresarial (sintetico)",
    "010501": "Licenciamento de software (sintetico)",
    "010101": "Desenvolvimento de sistemas (sintetico)",
    "071001": "Limpeza de imoveis (sintetico)",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    invoice: Invoice
    expected_divergent: frozenset[str] = frozenset()
    expected_errors: frozenset[str] = frozenset()


@dataclass
class InvoiceFactory:
    tables: TaxTables
    seed: int = 42
    _rng: random.Random = field(init=False)
    _number: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def compliant(
        self,
        *,
        competence: date,
        service_code: str = "170101",
        amount: str | Decimal = "1000.00",
        municipality: str = SYNTHETIC_MUNICIPALITY,
        simples: SimplesNacionalOption = SimplesNacionalOption.NOT_OPTANT,
        highlight_ibs_cbs: bool | None = None,
        iss_rate: Decimal | None = None,
        iss_amount: Decimal | None = None,
        withholdings: dict[str, Decimal] | None = None,
    ) -> Invoice:
        """A compliant invoice; the keyword overrides inject deliberate errors."""
        self._number += 1
        rng, tables = self._rng, self.tables
        amount = Decimal(amount)
        subitem = f"{service_code[:2]}.{service_code[2:4]}"
        provider = make_provider(
            seq=rng.randint(1, 999),
            simples=simples,
            name=f"{rng.choice(NAMES)} Servicos Sinteticos Ltda",
        )
        taker = make_taker(
            seq=rng.randint(1000, 1999), name=f"{rng.choice(NAMES)} Industria Sintetica SA"
        )

        if iss_rate is None:
            if simples is SimplesNacionalOption.MEI:
                iss_rate = Decimal(0)
            elif provider.is_simples_nacional:
                iss_rate = Decimal("0.02")
            else:
                iss_rate = tables.municipal_iss(municipality, competence).params.rates[subitem]
        is_mei = simples is SimplesNacionalOption.MEI
        iss = make_iss(
            base=amount,
            rate=iss_rate,
            amount=ZERO
            if is_mei
            else (iss_amount if iss_amount is not None else to_cents(amount * iss_rate)),
        )

        withheld = self._withholdings(provider.is_simples_nacional, subitem, amount, competence)
        withheld |= withholdings or {}
        pis_cofins = (
            make_pis_cofins(withheld["pis"], withheld["cofins"])
            if withheld["pis"] or withheld["cofins"]
            else None
        )

        ibs_cbs = None
        params = tables.ibs_cbs(competence).params
        wants_group = (
            params.is_mandatory_for(subitem) if highlight_ibs_cbs is None else highlight_ibs_cbs
        )
        if wants_group and not provider.is_simples_nacional:
            deductions = {"iss": iss.amount, "pis": withheld["pis"], "cofins": withheld["cofins"]}
            base = amount - sum((deductions[d] for d in params.base_deductions), ZERO)
            ibs_cbs = make_ibs_cbs(
                base=base,
                cbs_rate=params.cbs_rate if params.cbs_rate is not None else ILLUSTRATIVE_CBS_2027,
                ibs_state_rate=params.ibs_state_rate,
                ibs_municipal_rate=params.ibs_municipal_rate,
            )

        issued_at = datetime(
            competence.year,
            competence.month,
            rng.randint(2, 21),
            rng.randint(8, 18),
            rng.randint(0, 59),
            tzinfo=BRT,
        )
        service = make_service(
            code=service_code, description=SERVICES.get(service_code, "Servico sintetico")
        )
        return make_invoice(
            access_key=synthetic_access_key(municipality, provider.cnpj, self._number, competence),
            number=str(self._number),
            issued_at=issued_at,
            competence_date=competence,
            provider=provider,
            taker=taker,
            service=service.model_copy(update={"incidence_municipality_code": municipality}),
            service_amount=amount,
            iss=iss,
            withholdings=make_withholdings(**withheld),
            pis_cofins=pis_cofins,
            ibs_cbs=ibs_cbs,
        )

    def _withholdings(
        self, is_simples: bool, subitem: str, amount: Decimal, competence: date
    ) -> dict[str, Decimal]:
        result = {"irrf": ZERO, "pis": ZERO, "cofins": ZERO, "csll": ZERO}
        if is_simples:
            return result
        irrf = self.tables.irrf(competence).params
        if (group := irrf.rate_for(subitem)) is not None:
            value = to_cents(amount * group.rate)
            result["irrf"] = value if value > irrf.min_amount else ZERO
        federal = self.tables.federal_withholding(competence).params
        if subitem in federal.subitems:
            values = {tax: to_cents(amount * rate) for tax, rate in federal.rates.items()}
            if sum(values.values(), ZERO) > federal.min_total:
                result |= values
        return result


def scenarios(factory: InvoiceFactory) -> list[Scenario]:
    f = factory
    d = Decimal
    cbs_pending = frozenset({"CBS_AMOUNT"})

    def wrong_base(invoice: Invoice) -> Invoice:
        info = invoice.ibs_cbs
        assert info is not None
        group = make_ibs_cbs(
            invoice.service_amount, info.cbs_rate, info.ibs_state_rate, info.ibs_municipal_rate
        )
        return invoice.model_copy(update={"ibs_cbs": group})

    def rates_2026(invoice: Invoice) -> Invoice:
        info = invoice.ibs_cbs
        assert info is not None
        return invoice.model_copy(
            update={"ibs_cbs": make_ibs_cbs(info.base, "0.009", "0.001", "0")}
        )

    return [
        Scenario(
            "compliant-2026-consulting",
            "Consulting, March 2026: every check passes; IBS/CBS still optional.",
            f.compliant(competence=date(2026, 3, 1)),
        ),
        Scenario(
            "compliant-2026-sp-software",
            "Software licensing in Sao Paulo (2.9%), December 2026, with IBS/CBS highlighted.",
            f.compliant(
                competence=date(2026, 12, 1),
                service_code="010501",
                amount="5000.00",
                municipality=SAO_PAULO,
            ),
        ),
        Scenario(
            "iss-wrong-municipal-rate",
            "Sao Paulo software taxed at 2% instead of 2.9%.",
            f.compliant(
                competence=date(2026, 6, 1),
                service_code="010501",
                amount="5000.00",
                municipality=SAO_PAULO,
                iss_rate=d("0.02"),
            ),
            frozenset({"ISS_RATE_MUNICIPAL"}),
        ),
        Scenario(
            "iss-rate-above-maximum",
            "ISS at 6%, above the 5% national maximum.",
            f.compliant(competence=date(2026, 4, 1), iss_rate=d("0.06")),
            frozenset({"ISS_RATE_RANGE", "ISS_RATE_MUNICIPAL"}),
        ),
        Scenario(
            "iss-amount-miscalculated",
            "ISS amount does not match base x rate.",
            f.compliant(competence=date(2026, 5, 1), iss_amount=d("45.00")),
            frozenset({"ISS_AMOUNT"}),
        ),
        Scenario(
            "irrf-not-withheld",
            "Professional service without the 1.5% IRRF withholding.",
            f.compliant(competence=date(2026, 5, 1), withholdings={"irrf": d("0.00")}),
            frozenset({"IRRF_WITHHOLDING"}),
        ),
        Scenario(
            "withholding-below-waiver",
            "R$ 200.00: PIS/COFINS/CSLL total 9.30 is waived, but was withheld anyway.",
            f.compliant(
                competence=date(2026, 7, 1),
                amount="200.00",
                withholdings={"pis": d("1.30"), "cofins": d("6.00"), "csll": d("2.00")},
            ),
            frozenset({"PIS_WITHHOLDING", "COFINS_WITHHOLDING", "CSLL_WITHHOLDING"}),
        ),
        Scenario(
            "simples-provider-with-withholding",
            "Simples Nacional provider with IRRF and CSLL wrongly withheld.",
            f.compliant(
                competence=date(2026, 4, 1),
                simples=SimplesNacionalOption.ME_EPP,
                withholdings={"irrf": d("15.00"), "csll": d("10.00")},
            ),
            frozenset({"IRRF_WITHHOLDING", "CSLL_WITHHOLDING"}),
        ),
        Scenario(
            "ibs-cbs-missing-when-mandatory",
            "November 2026: IBS/CBS group is mandatory for consulting but missing.",
            f.compliant(competence=date(2026, 11, 1), highlight_ibs_cbs=False),
            frozenset({"CBS_AMOUNT", "IBS_STATE_AMOUNT", "IBS_MUNICIPAL_AMOUNT"}),
        ),
        Scenario(
            "ibs-cbs-base-without-deductions",
            "IBS/CBS base equals the service value; in 2026 ISS, PIS and COFINS must be deducted.",
            wrong_base(f.compliant(competence=date(2026, 10, 1))),
            frozenset({"IBS_CBS_BASE"}),
        ),
        Scenario(
            "synthetic-city-rate-2026",
            "Synthetic city, subitem 1.05 at 2% in December 2026: correct for that date.",
            f.compliant(competence=date(2026, 12, 1), service_code="010501", amount="3000.00"),
        ),
        Scenario(
            "synthetic-city-old-rate-in-2027",
            "Same service in January 2027 still at 2%; the synthetic city raised it to 2.5%.",
            f.compliant(
                competence=date(2027, 1, 1),
                service_code="010501",
                amount="3000.00",
                iss_rate=d("0.02"),
            ),
            frozenset({"ISS_RATE_MUNICIPAL"}),
            cbs_pending,
        ),
        Scenario(
            "pis-cofins-withheld-in-2027",
            "PIS and COFINS withheld in 2027, after their extinction.",
            f.compliant(
                competence=date(2027, 2, 1),
                amount="2000.00",
                withholdings={"pis": d("13.00"), "cofins": d("60.00")},
            ),
            frozenset({"PIS_WITHHOLDING", "COFINS_WITHHOLDING"}),
            cbs_pending,
        ),
        Scenario(
            "compliant-2027",
            "March 2027: only CSLL withheld, IBS split 0.05% + 0.05%. CBS awaits the Senate rate.",
            f.compliant(competence=date(2027, 3, 1), amount="2000.00"),
            frozenset(),
            cbs_pending,
        ),
        Scenario(
            "mei-provider",
            "MEI provider: ISS paid in the DAS, no withholdings, no IBS/CBS checks.",
            f.compliant(
                competence=date(2026, 5, 1), amount="800.00", simples=SimplesNacionalOption.MEI
            ),
        ),
        Scenario(
            "2026-rates-on-2027-invoice",
            "2027 invoice still using the 2026 IBS rates (0.1% state, no municipal IBS).",
            rates_2026(f.compliant(competence=date(2027, 4, 1), amount="2000.00")),
            frozenset({"IBS_STATE_AMOUNT", "IBS_MUNICIPAL_AMOUNT"}),
            cbs_pending,
        ),
    ]


MALFORMED_DOCUMENTS = {
    "broken.xml": b"<NFSe xmlns='http://www.sped.fazenda.gov.br/nfse'><infNFSe>",
    "xxe-attempt.xml": (
        b'<?xml version="1.0"?>\n<!DOCTYPE NFSe [<!ENTITY x SYSTEM "file:///etc/passwd">]>\n'
        b"<NFSe xmlns='http://www.sped.fazenda.gov.br/nfse'>&x;</NFSe>"
    ),
}


def random_invoices(factory: InvoiceFactory, count: int) -> list[Invoice]:
    rng = random.Random(factory.seed + 1)
    months = [date(2026, m, 1) for m in range(1, 13)] + [date(2027, m, 1) for m in range(1, 7)]
    invoices = []
    for _ in range(count):
        code = rng.choice(["170101", "010101", "010501", "071001"])
        overrides: dict[str, Any] = {}
        if rng.random() < 0.3:
            overrides["iss_amount"] = Decimal(rng.randint(1, 30))
        invoices.append(
            factory.compliant(
                competence=rng.choice(months),
                service_code=code,
                amount=Decimal(rng.randint(100, 20000)).quantize(Decimal("0.01")),
                **overrides,
            )
        )
    return invoices


def generate(out_dir: Path, tables: TaxTables, seed: int = 42, extra: int = 0) -> dict[str, Any]:
    """Write scenario XMLs, random XMLs, malformed samples and a manifest.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    factory = InvoiceFactory(tables, seed)
    manifest: dict[str, Any] = {"seed": seed, "scenarios": [], "random": [], "malformed": []}
    for index, scenario in enumerate(scenarios(factory), start=1):
        filename = f"{index:03d}-{scenario.name}.xml"
        (out_dir / filename).write_bytes(to_nfse_xml(scenario.invoice))
        manifest["scenarios"].append(
            {
                "file": filename,
                "description": scenario.description,
                "expected_divergent": sorted(scenario.expected_divergent),
                "expected_errors": sorted(scenario.expected_errors),
            }
        )
    for index, invoice in enumerate(random_invoices(factory, extra), start=1):
        filename = f"random-{index:04d}.xml"
        (out_dir / filename).write_bytes(to_nfse_xml(invoice))
        manifest["random"].append(filename)
    for filename, content in MALFORMED_DOCUMENTS.items():
        (out_dir / filename).write_bytes(content)
        manifest["malformed"].append(filename)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

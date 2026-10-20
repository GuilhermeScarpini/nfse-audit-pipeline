"""Command line interface: generate synthetic data, audit a folder, validate XMLs."""

import argparse
import sys
import uuid
from pathlib import Path

from nfse_audit.extraction import ExtractionError
from nfse_audit.extraction.schema import validate
from nfse_audit.extraction.xml_security import parse_untrusted
from nfse_audit.pipeline import audit_documents
from nfse_audit.reporting import to_excel, to_json
from nfse_audit.rules.engine import RuleEngine
from nfse_audit.synthetic.generator import generate
from nfse_audit.tax_tables import TaxTables
from nfse_audit.worker.tasks import default_extractors


def _generate(args: argparse.Namespace) -> int:
    manifest = generate(args.out, TaxTables.from_directory(), seed=args.seed, extra=args.random)
    total = len(manifest["scenarios"]) + len(manifest["random"]) + len(manifest["malformed"])
    print(f"wrote {total} documents and manifest.json to {args.out}")
    return 0


def _audit(args: argparse.Namespace) -> int:
    paths = sorted(p for p in args.folder.iterdir() if p.suffix.lower() == ".xml")
    batch_id = uuid.uuid4().hex
    report = audit_documents(
        batch_id,
        ((p.name, p.read_bytes()) for p in paths),
        default_extractors(),
        RuleEngine(TaxTables.from_directory()),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"audit-{batch_id}.json").write_text(to_json(report), encoding="utf-8")
    (args.out / f"audit-{batch_id}.xlsx").write_bytes(to_excel(report))
    for key, value in report.summary.items():
        print(f"{key:>24}: {value}")
    print(f"reports written to {args.out} (audit-{batch_id}.json / .xlsx)")
    return 0


def _validate(args: argparse.Namespace) -> int:
    failures = 0
    for path in args.files:
        try:
            errors = validate(parse_untrusted(path.read_bytes()))
        except ExtractionError as exc:
            errors = [str(exc)]
        status = "ok" if not errors else "INVALID"
        print(f"{status:>8}  {path}")
        for error in errors[:5]:
            print(f"          {error}")
        failures += bool(errors)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nfse-audit", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="write synthetic NFS-e XMLs with known errors")
    gen.add_argument("--out", type=Path, default=Path("data/synthetic"))
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--random", type=int, default=0, help="extra random invoices")
    gen.set_defaults(handler=_generate)

    audit = commands.add_parser("audit", help="audit every .xml in a folder")
    audit.add_argument("folder", type=Path)
    audit.add_argument("--out", type=Path, default=Path("reports"))
    audit.set_defaults(handler=_audit)

    check = commands.add_parser("validate", help="validate XMLs against the NFS-e schema")
    check.add_argument("files", type=Path, nargs="+")
    check.set_defaults(handler=_validate)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

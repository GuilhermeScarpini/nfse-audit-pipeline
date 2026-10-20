# NFS-e Audit Pipeline

Asynchronous pipeline that audits Brazilian service invoices (NFS-e, national layout) against **tax rules versioned by effective date**, covering the 2026–2027 tax reform transition (IBS/CBS replacing PIS/COFINS).

> 🚧 Portfolio project, work in progress. **All data is synthetic.** Current status and next steps: [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md).

## What it does

```
POST /batches (XML files) ──► shared volume ──► Redis queue (batch id only) ──► worker
                                                                                  │
GET /batches/{id}          ◄── status in Redis ◄──────────────────────────────────┤
GET /batches/{id}/report   ◄── JSON / Excel report ◄── extract → rules → report ◄─┘
```

1. **Batch ingestion.** FastAPI receives a batch of NFS-e XMLs, stores them, and enqueues **only the batch id** (claim check pattern). The response is `202 Accepted` with a batch id. `Idempotency-Key` makes retries safe.
2. **Extraction.** National NFS-e XML (layout v1.01) is parsed into Pydantic models with hardened parsing: any DOCTYPE is rejected, which blocks XXE and billion-laughs attacks. The extractor interface is ready for other formats such as PDF.
3. **Deterministic rule engine.** Each rule is a pure function of the invoice and the tax tables. The table version in force is chosen by the invoice's **competence date**, so the same service is audited differently in 2026 and in 2027.
4. **Auditable reports.** JSON and Excel list every rule checked per invoice: expected value, found value, status (`ok` / `divergent` / `not_applicable` / `error`), legal basis, and the exact table version applied.

### Rules

| Rule | What it checks |
|---|---|
| `ISS_RATE_RANGE` | ISS between 2% and 5% (LC 116/2003) |
| `ISS_RATE_MUNICIPAL` | ISS rate matches the municipal table for the service |
| `ISS_AMOUNT` | ISS = base × rate |
| `IRRF_WITHHOLDING` | 1.5% / 1% by service type, R$ 10 waiver, Simples Nacional exemption |
| `PIS/COFINS/CSLL_WITHHOLDING` | Lei 10.833/2003; **from 2027 only CSLL** (LC 214/2025) |
| `IBS_CBS_BASE` | base net of ISS (and of PIS/COFINS in 2026) |
| `CBS/IBS_STATE/IBS_MUNICIPAL_AMOUNT` | 2026 test rates; 2027 split; mandatory from Oct/2026 |

Every table entry cites its legal basis and carries a `verified` flag. The **2027 CBS reference rate** has not been published by the Senate yet, so CBS checks for 2027 report `error` rather than guessing a value.

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run nfse-audit generate --out data/synthetic --random 20   # 16 scenarios + random + malformed
uv run nfse-audit audit data/synthetic --out reports           # JSON + Excel report
uv run nfse-audit validate data/synthetic/0*.xml               # official XSD v1.01
uv run pytest                                                  # 143 tests
```

### Full stack with Docker Compose

API + worker + Redis, with a shared volume for the batch documents:

```bash
docker compose up --build --wait                 # API on http://localhost:8000 (docs at /docs)
curl -F "files=@data/synthetic/001-compliant-2026-consulting.xml" http://localhost:8000/batches
curl http://localhost:8000/batches/<batch_id>                     # queued → processing → done
curl -o audit.xlsx "http://localhost:8000/batches/<batch_id>/report?format=xlsx"
./scripts/smoke-test.sh                          # end-to-end check, also run in CI
```

The image is multi-stage (uv only in the build stage) and runs as a non-root user. Behind a TLS-inspecting proxy, see [`docker-compose.override.example.yml`](docker-compose.override.example.yml).

## Synthetic data

- **CNPJs start with `SY`.** That is the alphanumeric CNPJ format, valid since July 2026, so these numbers cannot clash with a real numeric CNPJ.
- **The demo municipality `9999999` does not exist.** It is used to demonstrate a rate change on 2027-01-01.
- **Documents are unsigned** and marked as the test environment (`tpAmb=2`).
- **Each scenario lists the rules it must flag** (`manifest.json`), and the test suite checks this end to end.

## Official schemas

The national NFS-e XSD v1.01 is vendored byte-for-byte, with provenance and hashes. Three adaptations are applied in memory, each documented in [`SOURCE.md`](src/nfse_audit/extraction/schemas/v1.01/SOURCE.md):

- alphanumeric CNPJ;
- signature made optional, for the unsigned synthetic documents;
- a fix for an invalid `^…$` pattern in `TSSerieDPS`, which makes standards-conforming validators reject every series.

## Tech stack

Python 3.12 · FastAPI · Redis + RQ · Pydantic v2 · lxml · openpyxl · pytest · uv · Docker Compose · GitHub Actions

## Architecture decisions

See [`docs/adr/`](docs/adr/).

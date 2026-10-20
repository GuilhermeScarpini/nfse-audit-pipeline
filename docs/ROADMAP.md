# Roadmap do MVP

> Status atual de cada fase e próximos passos: [NEXT_STEPS.md](NEXT_STEPS.md).

Plano de implementação em fases. Ordem escolhida: **de dentro para fora** — primeiro o núcleo de domínio (modelos, extração, regras), sem I/O; a infraestrutura (API, fila, Docker) vem por último.

## Fluxo alvo

```
POST /batches (vários XMLs)
   │  salva os arquivos em volume compartilhado, cria o lote com status "queued"
   │  enfileira um job no Redis com a REFERÊNCIA aos arquivos
   └─► 202 Accepted  { "batch_id": "..." }

worker
   └─► extração (XML → Pydantic) → motor de regras (tabelas pela data de competência)
       → resultado por regra: esperado / encontrado / status → lote "done"

GET /batches/{id}                     → status e progresso
GET /batches/{id}/report?format=json  → relatório JSON
GET /batches/{id}/report?format=xlsx  → relatório Excel
```

## Decisões de escopo

- **Reforma tributária:** competências de **2026 e 2027**. Em 2026, ano de teste de IBS/CBS, com PIS/COFINS vigentes; a partir de 2027, a CBS substitui PIS/COFINS. As regras são selecionadas pela data de competência da nota, e cada tabela cita sua base legal.
- Status de cada regra: `ok`, `divergent`, `not_applicable`.
- Regras federais com base legal real; ISS de poucos municípios reais com a lei citada, mais uma mudança de vigência **sintética e rotulada como tal** para demonstrar o versionamento.
- Apenas dados sintéticos.

## Fases

| Fase | Entrega | Conceitos |
|---|---|---|
| 0 — Fundação | `pyproject.toml`, layout `src/`, pytest, ruff, `.gitattributes`, `.env.example`, CI, ADRs 0001–0002 | layout `src/`, ambiente virtual, lockfile, CI |
| 1 — Domínio | Modelos Pydantic imutáveis, `Money` (Decimal), `Cnpj` com dígito verificador | validators Pydantic v2, por que não usar `float` para dinheiro |
| 2 — Dados sintéticos | Gerador com seed fixa, cenários com erros propositais, XML no layout nacional validado contra o XSD oficial | anatomia do XML da NFS-e, XSD, geração determinística |
| 3 — Extração | Interface `InvoiceExtractor` + `NationalXmlExtractor`, teste de ida e volta | Strategy / `Protocol`, segurança de XML (XXE, billion laughs) |
| 4 — Tabelas versionadas | Tabelas YAML com `valid_from`/`valid_to` e base legal, resolução por data de competência | versionamento temporal, competência × emissão × processamento |
| 5 — Motor de regras | ISS, IRRF, PIS, COFINS, CSLL; resultado com versão da tabela usada | funções puras, arredondamento e tolerância, testes parametrizados |
| 6 — Relatórios e CLI | JSON, Excel, `nfse-audit audit ./pasta` | separar cálculo de apresentação |
| 7 — API, fila e worker | Endpoints de lote, worker, deduplicação, limites de upload | fila assíncrona, claim check, idempotência, at-least-once, `Depends` |
| 8 — Docker Compose | Dockerfile multi-stage, Compose com api + worker + Redis | camadas de imagem, usuário não-root, healthchecks |
| 9 — Portfólio | README com demo e diagrama, varredura de segredos no histórico, tornar público | higiene de segurança antes de abrir o repositório |

## Fora do MVP

Extração de PDF · reduções e regimes específicos de IBS/CBS · transição do ISS a partir de 2029 · retenção de INSS · Postgres · autenticação · interface web · muitos municípios.

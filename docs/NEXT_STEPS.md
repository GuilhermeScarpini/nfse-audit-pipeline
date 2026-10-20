# Estado do projeto e próximos passos

_Atualizado em 2026-10-20._

## Onde estamos

| Fase | Status | Observação |
|---|---|---|
| 0 — Fundação | ✅ | uv, pytest, ruff, CI, ADRs |
| 1 — Domínio | ✅ | `Decimal`, CNPJ alfanumérico, CNPJs sintéticos com prefixo `SY` |
| 2 — Dados sintéticos | ✅ | 16 cenários com erros propositais, notas aleatórias, amostras malformadas e XXE |
| 3 — Extração | ✅ | XSD oficial v1.01 com 3 adaptações documentadas; parser seguro |
| 4 — Tabelas versionadas | ✅ | federal, ISS de São Paulo e município sintético com mudança de alíquota em 2027 |
| 5 — Motor de regras | ✅ | ISS, IRRF, PIS/COFINS/CSLL, IBS/CBS (2026 e 2027) |
| 6 — Relatórios e CLI | ✅ | JSON, Excel, `nfse-audit generate / audit / validate` |
| 7 — API, fila e worker | ✅ | testado com Redis em memória; [ADR-0004](adr/0004-async-batch-processing-with-rq.md) |
| 8 — Docker Compose | 🟡 | escrito na branch `wip/docker`, **nunca executado** |
| 9 — Portfólio | ⬜ | ainda não começou |

Hoje há 143 testes passando, localmente e no CI.

## Como retomar uma sessão

1. Abra a pasta `nfse-audit-pipeline` no VS Code. O `CLAUDE.md` só é carregado quando a sessão começa dentro dela.
2. Rode:
   ```bash
   uv sync
   uv run pytest
   ```
3. Peça ao Claude: "leia docs/NEXT_STEPS.md e continue pelo próximo passo".

## Próximos passos, em ordem

### 1. Terminar a Fase 8 (Docker)

O código está na branch `wip/docker`: Dockerfile multi-stage, `docker-compose.yml` (api + worker + redis), `scripts/smoke-test.sh` e um job `docker` no CI.

**Caminho mais rápido, sem precisar do Docker local.** O CI do GitHub tem Docker e roda o teste de fumaça em pull requests:

```bash
git push -u origin wip/docker
gh pr create --base main --head wip/docker --title "feat(infra): Docker Compose stack" --body "Runs the smoke test in CI"
gh pr checks --watch
```

Se o job `docker` passar, faça o merge (`gh pr merge --squash`). Se falhar, `gh run view --log-failed` mostra o erro.

**Para rodar localmente:** `docker compose up --build --wait` e depois `./scripts/smoke-test.sh`.

### 2. Alíquota da CBS de 2027

O Senado deve publicar a alíquota de referência até 15/12/2026 (LC 214/2025, arts. 349 e 353). Quando sair:
1. Em `src/nfse_audit/tax_tables/tables/federal/ibs_cbs.yaml`, versão `2027-01-01`:
   - preencha `cbs_rate` com a referência menos 0,1 p.p. (art. 347);
   - cite a resolução em `legal_basis`;
   - mude `verified` para `true`.
2. Em `src/nfse_audit/synthetic/generator.py`:
   - troque `ILLUSTRATIVE_CBS_2027` pela alíquota real;
   - remova `cbs_pending` dos cenários de 2027.
3. Ajuste `tests/unit/rules/test_ibs_cbs.py`. O teste `test_2027_cbs_is_an_error_until_the_reference_rate_is_published` vai falhar de propósito: transforme-o num teste de valor correto.

Esse é o melhor exemplo do versionamento temporal: a mudança de lei é uma alteração de dados com base legal, não de código.

### 3. Itens marcados `verified: false`

- Mapeamento das categorias do RIR (arts. 714 e 716) e da Lei 10.833 (art. 30) para subitens da LC 116 (`irrf.yaml`, `federal_withholding.yaml`). É uma simplificação e precisa de revisão.
- A dispensa de R$ 10 para a CSLL a partir de 2027 foi deduzida pela técnica de redação da LC 214/2025, art. 509. Confirmar em regulamentação da RFB.
- A não retenção de IRRF para o Simples (IN RFB 765/2007) foi confirmada só em fonte secundária.

### 4. Evolução do layout

- **NT 009 (layout v1.04.01):** ainda sem XSD publicado. Quando sair, adicione `schemas/v1.04/` e faça o extrator escolher o schema pelo atributo `versao`.
- **Simples Nacional:** a NT 009 traz o grupo `gTribSN`, com IBS/CBS do Simples a partir de 2027. Hoje as regras de IBS/CBS retornam `not_applicable` para o Simples.
- **Ato Conjunto RFB/CGIBS 4/2026:** outras categorias com obrigatoriedade em 01/12/2026 (plataformas digitais, condomínios, locações) não estão modeladas.

### 5. Fase 9 — Portfólio

- Varredura de segredos em todo o histórico: `gitleaks detect --source . --log-opts="--all"`.
- Diagrama de arquitetura no README e um GIF ou passo a passo da demo com Docker.
- Revisão final e só então tornar o repositório público:
  ```bash
  gh repo edit --visibility public --accept-visibility-change-consequences
  ```

### 6. Depois do MVP

Extrator de PDF (nova implementação de `InvoiceExtractor`), Postgres para status e relatórios, armazenamento de objetos para os documentos, retenção de INSS, autenticação na API e mais municípios.

## Observações

- **O worker do RQ usa `fork`** e não roda nativamente no Windows; ele roda em container (Fase 8). Os testes de integração não dependem disso.
- **Diário de aprendizado local:** `aprendizado/`, fora do git. Só existe o arquivo da Fase 0; os das Fases 1 a 8 estão pendentes. Peça ao Claude para escrevê-los.

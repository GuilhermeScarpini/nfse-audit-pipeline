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
| 8 — Docker Compose | ✅ | imagem multi-stage, api + worker + redis, teste de fumaça no CI; [ADR-0005](adr/0005-container-image-and-compose-stack.md) |
| 9 — Portfólio | ⬜ | ainda não começou |

Hoje há 143 testes passando, localmente e no CI, e o CI sobe a stack Docker e roda `scripts/smoke-test.sh`.

## Como retomar uma sessão

1. Abra a pasta `nfse-audit-pipeline` no VS Code. O `CLAUDE.md` só é carregado quando a sessão começa dentro dela.
2. Rode:
   ```bash
   uv sync
   uv run pytest
   ```
3. Peça ao Claude: "leia docs/NEXT_STEPS.md e continue pelo próximo passo".

## Próximos passos, em ordem

### 1. Alíquota da CBS de 2027

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

### 2. Itens marcados `verified: false`

- Mapeamento das categorias do RIR (arts. 714 e 716) e da Lei 10.833 (art. 30) para subitens da LC 116 (`irrf.yaml`, `federal_withholding.yaml`). É uma simplificação e precisa de revisão.
- A dispensa de R$ 10 para a CSLL a partir de 2027 foi deduzida pela técnica de redação da LC 214/2025, art. 509. Confirmar em regulamentação da RFB.
- A não retenção de IRRF para o Simples (IN RFB 765/2007) foi confirmada só em fonte secundária.

### 3. Evolução do layout

- **NT 009 (layout v1.04.01):** ainda sem XSD publicado. Quando sair, adicione `schemas/v1.04/` e faça o extrator escolher o schema pelo atributo `versao`.
- **Simples Nacional:** a NT 009 traz o grupo `gTribSN`, com IBS/CBS do Simples a partir de 2027. Hoje as regras de IBS/CBS retornam `not_applicable` para o Simples.
- **Ato Conjunto RFB/CGIBS 4/2026:** outras categorias com obrigatoriedade em 01/12/2026 (plataformas digitais, condomínios, locações) não estão modeladas.

### 4. Fase 9 — Portfólio

- Varredura de segredos em todo o histórico: `gitleaks detect --source . --log-opts="--all"`.
- Fixar as imagens base por digest e ativar o Dependabot (pip, Docker e GitHub Actions).
- Diagrama de arquitetura no README e um GIF ou passo a passo da demo com Docker.
- Revisão final e só então tornar o repositório público:
  ```bash
  gh repo edit --visibility public --accept-visibility-change-consequences
  ```

### 5. Depois do MVP

Extrator de PDF (nova implementação de `InvoiceExtractor`), Postgres para status e relatórios, armazenamento de objetos para os documentos, retenção de INSS, autenticação na API e mais municípios.

## Observações

- **O worker do RQ usa `fork`** e não roda nativamente no Windows; ele roda em container. Os testes de integração não dependem disso.
- **Build atrás de um proxy que inspeciona TLS:** salve a CA raiz como `extra-ca.crt` na raiz do projeto e copie `docker-compose.override.example.yml` para `docker-compose.override.yml`. Os dois estão no `.gitignore`; **nunca commite o certificado**.
- **Diário de aprendizado local:** `aprendizado/`, fora do git. Ele se perdeu quando o repositório foi clonado de novo (junto com a branch `wip/docker`, que nunca foi enviada ao GitHub). Hoje existe o arquivo da Fase 8; os das Fases 0 a 7 precisam ser reescritos. Peça ao Claude.

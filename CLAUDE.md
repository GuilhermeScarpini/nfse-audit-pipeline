# CLAUDE.md

Instruções permanentes para o Claude Code neste repositório. Valem para todas as sessões.

## Contexto do projeto

**NFS-e Audit Pipeline** — projeto de portfólio: pipeline de auditoria de NFS-e (Nota Fiscal de Serviço eletrônica) e conformidade tributária.

- Ingestão assíncrona de lotes de XML (FastAPI + fila Redis + worker).
- Parsing do XML no padrão nacional da NFS-e para modelos Pydantic.
- Motor de regras determinístico (ISS, IRRF, PIS/COFINS/CSLL) com tabelas tributárias versionadas por data de vigência.
- Relatórios auditáveis (JSON e Excel) por nota: regra, valor esperado, valor encontrado, status.
- Apenas dados sintéticos, gerados pelo próprio projeto.

## Modo de trabalho: velocidade máxima + diário de aprendizado (obrigatório)

O dono do projeto quer velocidade **e** aprendizado. Portanto:

- **Execute direto.** Implemente fases inteiras sem parar a cada passo. Pare apenas para decisões que são genuinamente do usuário (escopo, preferência, custo) ou para ações arriscadas/irreversíveis.
- **Todo o conteúdo didático vai para `aprendizado/`** (pasta local, no `.gitignore`, **nunca vai para o GitHub**). Um arquivo por fase: `aprendizado/fase-NN-nome.md`, indexados em `aprendizado/README.md`. Cada arquivo de fase contém:
  1. **O que foi feito** — resumo do que entrou, com links para os arquivos.
  2. **Conceitos** — cada conceito novo (ex.: fila assíncrona, idempotência, versionamento temporal, injeção de dependência no FastAPI) explicado em poucas frases, com um exemplo concreto do próprio projeto.
  3. **Decisões e trade-offs** — alternativas consideradas e por que uma foi escolhida (com link para o ADR, se houver).
  4. **Armadilhas encontradas** — erros e pegadinhas que apareceram durante a implementação e como foram resolvidos.
  5. **Como testar** — comandos para o usuário rodar e o que esperar.
  6. **Desafios opcionais** — 1 a 3 exercícios pequenos (ex.: "escreva o teste para esta regra") para o usuário fazer quando quiser.
- **No chat, seja breve:** ao fim de cada fase, um resumo curto e o link para o arquivo de aprendizado da fase.
- **ADRs continuam obrigatórios** para decisões relevantes de arquitetura, em `docs/adr/` (formato abaixo). Esses vão para o GitHub.
- **Aponte más práticas.** Se o usuário pedir algo que seja má prática, diga e explique, em vez de só obedecer.
- **Idiomas.** Explicações, comentários, ADRs, README e `aprendizado/` em português (o público do projeto está no Brasil); código, nomes de variáveis, nomes de arquivos e mensagens de commit em inglês.

## Convenções do projeto

### Stack
- Python 3.12
- FastAPI
- Redis (fila)
- Pydantic v2
- Docker / Docker Compose

### Testes
- pytest.
- **Toda regra tributária precisa de teste.** Nenhuma regra entra sem teste cobrindo pelo menos o caso conforme e o caso divergente.

### Commits
- Commits pequenos e semânticos, seguindo [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`, `ci:`...).
- Registre no arquivo de aprendizado da fase quais commits foram feitos e por que foram separados assim.
- Push para `origin/main` ao final de cada fase, com testes e lint passando.

### Dados e segredos
- **NUNCA commitar dados reais**: nada de CNPJs, CPFs, nomes, razões sociais ou notas verdadeiras. Use apenas dados sintéticos gerados no próprio projeto.
- Segredos só em `.env`, que deve estar no `.gitignore`. Mantenha um `.env.example` atualizado, sem valores sensíveis.

## Formato de ADR

Arquivos em `docs/adr/NNNN-titulo-curto.md` (ex.: `0001-use-redis-as-queue.md`), com as seções:

- **Status** — proposto / aceito / substituído por ADR-XXXX
- **Contexto** — qual problema ou força motivou a decisão
- **Alternativas consideradas** — cada uma com prós e contras
- **Decisão** — o que foi escolhido
- **Consequências** — o que fica mais fácil, o que fica mais difícil

## Comandos

```bash
uv sync                      # cria/atualiza o .venv a partir do uv.lock
uv run pytest                # todos os testes
uv run pytest tests/unit     # só os testes unitários
uv run ruff check .          # lint
uv run ruff format .         # formatação

uv run nfse-audit generate --out data/synthetic --random 20   # dados sintéticos
uv run nfse-audit audit data/synthetic --out reports          # auditoria local (JSON + Excel)
uv run nfse-audit validate data/synthetic/0*.xml              # valida no XSD oficial
```

## Estado atual

Antes de começar qualquer trabalho, leia [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md): status de cada fase, próximos passos em ordem e observações de ambiente. Atualize esse arquivo ao final de cada fase.

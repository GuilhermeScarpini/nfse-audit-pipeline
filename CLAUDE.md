# CLAUDE.md

Instruções permanentes para o Claude Code neste repositório. Valem para todas as sessões.

## Contexto do projeto

**NFS-e Audit Pipeline** — projeto de portfólio: pipeline de auditoria de NFS-e (Nota Fiscal de Serviço eletrônica) e conformidade tributária.

- Ingestão assíncrona de lotes de XML (FastAPI + fila Redis + worker).
- Parsing do XML no padrão nacional da NFS-e para modelos Pydantic.
- Motor de regras determinístico (ISS, IRRF, PIS/COFINS/CSLL) com tabelas tributárias versionadas por data de vigência.
- Relatórios auditáveis (JSON e Excel) por nota: regra, valor esperado, valor encontrado, status.
- Apenas dados sintéticos, gerados pelo próprio projeto.

## Modo didático (obrigatório)

O dono do projeto está usando este repositório para aprender. Portanto:

- **Explique antes de fazer.** Sempre diga o que vai fazer e por quê ANTES de executar.
- **Conceitos novos primeiro.** Ao introduzir um conceito novo (ex.: fila assíncrona, idempotência, versionamento temporal, injeção de dependência no FastAPI), explique-o em poucas frases, com um exemplo concreto, antes de aplicá-lo.
- **Decisões de arquitetura com alternativas.** Apresente as alternativas consideradas e o trade-off de cada uma. Registre decisões relevantes como ADRs em `docs/adr/` (formato abaixo).
- **Passos pequenos.** Ao final de cada passo, faça um resumo curto:
  1. O que foi feito.
  2. O que eu deveria entender.
  3. Como testar.
- **Desafios.** De vez em quando, proponha um pequeno desafio (ex.: "tente escrever o teste para esta regra") em vez de fazer tudo sozinho.
- **Aponte más práticas.** Se eu pedir algo que seja má prática, diga e explique, em vez de só obedecer.
- **Idiomas.** Explicações e comentários em português; código, nomes de variáveis, nomes de arquivos e mensagens de commit em inglês.

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
- Commits pequenos e semânticos, seguindo [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`...).
- Explique cada commit (o que entra e por quê) antes de fazê-lo.

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

_(A preencher conforme o projeto evoluir: subir o ambiente, rodar testes, gerar dados sintéticos.)_

# ADR-0002: Usar uv para gerenciar dependências e ambiente

- **Status:** aceito
- **Data:** 2026-10-20

## Contexto

O projeto roda em três ambientes: a máquina de desenvolvimento (Windows), o CI (GitHub Actions, Linux) e os containers Docker (Linux). Os três precisam instalar exatamente as mesmas versões de dependências, inclusive as transitivas. Sem isso, um teste pode passar localmente e falhar no CI ou no container.

Também queremos separar dependências de execução (FastAPI, Redis, Pydantic) das de desenvolvimento (pytest, ruff).

## Alternativas consideradas

- **pip + venv + requirements.txt** — já vem com o Python e é universalmente conhecido. Não tem lockfile nativo (exigiria `pip-tools`), e o ambiente virtual é gerenciado manualmente.
- **Poetry** — maduro, com lockfile, muito usado. É mais lento na resolução e na instalação, e tem convenções próprias.
- **uv** — muito rápido, com lockfile multiplataforma (`uv.lock`), `pyproject.toml` no padrão PEP 621, gerencia versões do Python e se integra bem a Docker e CI. Precisa ser instalado e é mais recente que as alternativas.

## Decisão

Usar **uv**. As dependências ficam declaradas no `pyproject.toml`, as versões exatas ficam no `uv.lock` (versionado no git), e as ferramentas de desenvolvimento ficam em um grupo de dependências separado.

## Consequências

- `uv sync` reproduz o ambiente de forma idêntica no Windows, no CI e no Docker.
- A instalação rápida reduz o tempo de CI e de build das imagens.
- Quem clonar o repositório precisa instalar o uv. O README vai documentar isso.
- Se o uv deixar de ser viável, a migração é barata: o `pyproject.toml` segue o padrão e funciona com pip.

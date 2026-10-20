# ADR-0001: Registrar decisões de arquitetura

- **Status:** aceito
- **Data:** 2026-10-20

## Contexto

Este projeto envolve várias decisões com trade-offs reais (fila, formato das tabelas tributárias, armazenamento de resultados, ferramentas). Sem registro, o raciocínio por trás de cada escolha se perde, e decisões são revisitadas sem saber por que foram tomadas. O projeto também tem objetivo didático e de portfólio: o porquê das escolhas é tão importante quanto o código.

## Alternativas consideradas

- **Não registrar** — zero custo imediato; o contexto se perde e as decisões viram "sempre foi assim".
- **Wiki ou documento externo** — fácil de editar; fica fora do repositório e desatualiza sem ninguém perceber.
- **ADRs em Markdown no repositório** — versionados junto com o código e revisados no mesmo fluxo de commit; exigem disciplina para escrever.

## Decisão

Registrar decisões relevantes como ADRs em `docs/adr/NNNN-titulo-curto.md`, com as seções Status, Contexto, Alternativas consideradas, Decisão e Consequências.

Um ADR aceito não é editado. Se a decisão mudar, um novo ADR o substitui, e o antigo passa ao status "substituído por ADR-XXXX".

## Consequências

- O histórico de decisões fica auditável e versionado, coerente com o propósito do projeto.
- Cada decisão de arquitetura passa a custar alguns minutos de escrita.
- Nem toda escolha vira ADR: apenas as que afetam a estrutura do sistema ou são caras de reverter.

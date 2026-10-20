# ADR-0004: Processamento assíncrono de lotes com RQ, claim check e status no Redis

- **Status:** aceito
- **Data:** 2026-10-20

## Contexto

Um lote pode ter centenas de XMLs. Processá-lo dentro da requisição HTTP deixaria o cliente esperando, sujeito a timeout, e acoplaria a disponibilidade da API ao custo da auditoria. O MVP usa Redis como fila (decisão de escopo).

## Alternativas consideradas

**Biblioteca de fila**
- **RQ** — simples, madura, feita para Redis, retry e timeout embutidos. O worker depende de `fork` (só Linux/macOS).
- **arq** — assíncrona (asyncio); em modo de manutenção.
- **Celery** — robusta e cheia de recursos; pesada demais para um worker e uma fila.
- **Redis puro (listas + BLMOVE)** — didático; reimplementa retry, timeout e monitoramento.

**O que vai na mensagem da fila**
- O conteúdo dos XMLs — simples; mensagens grandes sobrecarregam o Redis, que guarda tudo em memória.
- **Só uma referência (claim check)** — a mensagem leva o `batch_id`; os arquivos ficam num volume compartilhado.

**Onde guardar status e resultado**
- Banco relacional — durável e consultável; mais uma peça de infraestrutura no MVP.
- **Status no Redis + relatório JSON no volume** — sem infraestrutura nova; durabilidade depende do volume e da persistência do Redis.

## Decisão

- **RQ** como fila. O worker roda em container Linux (Docker), então a limitação de `fork` no Windows não importa.
- **Claim check:** a API salva os documentos em `<data_dir>/batches/<id>/input/` e enfileira apenas o `batch_id`.
- **Status no Redis** (`queued → processing → done | failed`) e **relatório JSON no volume**. O Excel é gerado sob demanda a partir do JSON.
- **Idempotência em duas camadas:**
  - Header `Idempotency-Key`: ligado ao `batch_id` com `SET NX` (atômico). Reenviar a mesma requisição devolve o lote original.
  - O job é idempotente por construção (entrega "pelo menos uma vez"): reprocessar lê as mesmas entradas e sobrescreve o mesmo relatório. O `job_id` derivado do lote impede enfileirar o mesmo lote duas vezes.
- **Retry:** até 3 tentativas (10 s, 30 s, 60 s).
- **Injeção de dependência:** a API recebe fila e armazenamentos via `Depends`; os testes usam Redis em memória e uma fila que executa o job no mesmo processo.

## Consequências

- A API responde em milissegundos (`202 Accepted`), independente do tamanho do lote.
- API e worker precisam compartilhar o volume de dados.
- Se o volume ou o Redis forem perdidos, perdem-se lotes. Para produção, o próximo passo seria Postgres para status e relatórios, e armazenamento de objetos (S3) para os documentos.
- O worker não roda nativamente no Windows; o desenvolvimento local do worker usa Docker.

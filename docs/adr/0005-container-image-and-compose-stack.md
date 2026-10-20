# ADR-0005: Imagem única multi-stage e stack com Docker Compose

- **Status:** aceito
- **Data:** 2026-10-20

## Contexto

A [ADR-0004](0004-async-batch-processing-with-rq.md) colocou o worker do RQ em container, porque ele depende de `fork` e não roda no Windows. A API, o worker e o Redis precisam subir juntos, compartilhar o volume de documentos (claim check) e ser testados de ponta a ponta. O build também precisa funcionar atrás de proxies que inspecionam TLS.

## Alternativas consideradas

**Quantas imagens**
- **Uma imagem para API e worker**, mudando só o comando — um build, mesmas dependências e mesma versão do código nos dois lados; a API carrega o RQ sem usar, e o worker carrega o FastAPI.
- Uma imagem por serviço — imagens um pouco menores; dois builds e o risco de API e worker rodarem versões diferentes das tabelas tributárias.

**Como montar a imagem**
- **Multi-stage com uv** — o uv e o cache ficam no estágio de build; o runtime leva só o Python e o `.venv`. As dependências ficam numa camada separada, que só é refeita quando o `uv.lock` muda.
- Estágio único com `pip install` — mais simples; imagem maior, sem lockfile e com ferramentas de build em produção.

**CA extra no build (proxy que inspeciona TLS)**
- `COPY` do certificado — funciona, mas grava o certificado numa camada e incentiva commitá-lo.
- `--build-arg` com o conteúdo — fica no histórico da imagem (`docker history`).
- **Build secret (`--mount=type=secret`)** — disponível só durante o `RUN`; não vai para nenhuma camada. É opcional: sem o secret, o build usa as CAs públicas (caso do CI).

**Como validar**
- Testar só com Redis em memória — rápido, mas não exercita o volume compartilhado, o worker real nem a imagem.
- **Teste de fumaça com a stack real** (`scripts/smoke-test.sh`), rodando no CI — cobre a imagem, o Compose, a fila, o worker e os relatórios; leva cerca de 30 s.

## Decisão

- **Uma imagem multi-stage**, construída com uv a partir do `uv.lock` (`--locked`). O projeto é instalado como pacote (não editável), então o runtime não precisa do código-fonte.
- O runtime roda como **usuário não root** (uid 10001). O `.venv` pertence ao root: o processo executa o código, mas não consegue alterá-lo.
- **Compose** com três serviços: `api` (uvicorn), `worker` (`rq worker --with-scheduler`, necessário para os retries com intervalo) e `redis` (com AOF, para o status sobreviver a um reinício).
- A porta da API é publicada **só em `127.0.0.1`**, porque a API ainda não tem autenticação.
- Uma CA extra, quando necessária, entra por **build secret**, configurado num `docker-compose.override.yml` local (no `.gitignore`). O repositório traz só o exemplo.
- O **CI roda o teste de fumaça** em todo push e pull request, depois dos testes unitários.

## Consequências

- `docker compose up --build --wait` sobe a stack inteira, e o CI garante que ela continua funcionando.
- Não é preciso ter o Docker local funcionando para validar mudanças de infraestrutura: o CI faz isso.
- As imagens base usam tags (`python:3.12-slim-trixie`, `uv:0.13.0`, `redis:8.2-alpine`), não digests. Isso é reprodutível o bastante para o MVP. Para produção, o próximo passo é fixar por digest e atualizar com o Dependabot.
  - *Atualização (Fase 9):* as imagens passaram a ser fixadas por digest (`tag@sha256:…`), e o Dependabot propõe as atualizações.
- A API e o worker sempre têm as mesmas dependências. Se um dia o worker precisar de algo pesado (ex.: OCR para PDF), vale separar as imagens.

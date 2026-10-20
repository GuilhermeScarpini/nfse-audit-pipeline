# ADR-0003: Modelo de domínio — Decimal e fronteira de validação

- **Status:** aceito
- **Data:** 2026-10-20

## Contexto

O sistema compara valores tributários ao centavo. Também precisa decidir o que fazer com uma nota inconsistente: rejeitá-la na leitura ou aceitá-la e reportar a divergência.

## Alternativas consideradas

**Representação de valores**
- `float` — nativo e rápido; não representa 0,10 com exatidão (`0.1 + 0.2 != 0.3`), o que gera divergências falsas de centavos.
- Inteiros em centavos — exatos; alíquotas como 0,65% exigiriam outra escala, e o código fica menos legível.
- `Decimal` — exato em base 10, com controle explícito de arredondamento; um pouco mais verboso.

**Fronteira de validação**
- Rejeitar qualquer inconsistência no modelo — o modelo fica "sempre correto", mas uma nota com ISS errado nunca chegaria ao relatório, e é exatamente isso que queremos auditar.
- Aceitar tudo — o motor de regras teria que se defender de dados estruturalmente impossíveis.

## Decisão

- Valores monetários e alíquotas são `Decimal`. `float` é **rejeitado** na entrada, nunca convertido silenciosamente.
- Dinheiro: não negativo, no máximo 2 casas decimais. Um valor com mais casas é rejeitado (não arredondado), porque arredondar em silêncio esconderia o dado original.
- Alíquotas são frações (0,05 = 5%). A conversão do percentual do XML é responsabilidade do extrator.
- O modelo rejeita apenas dados **estruturalmente impossíveis** (CNPJ malformado, valor negativo, campo desconhecido). Inconsistências de negócio (ISS calculado errado, retenção indevida) são aceitas e reportadas pelo motor de regras.
- Modelos imutáveis (`frozen`): uma nota lida não muda durante a auditoria.
- CNPJ alfanumérico (IN RFB 2.229/2024) é suportado. Dados sintéticos usam o prefixo `SY`, reconhecível e sem risco prático de colidir com CNPJs reais.

## Consequências

- Nenhuma divergência falsa causada por ponto flutuante.
- Quem constrói o modelo precisa passar `str`, `int` ou `Decimal`, o que gera um pouco mais de atrito nos testes.
- Uma nota com CNPJ inválido falha na extração e aparece no relatório como erro de leitura, não como divergência de regra.

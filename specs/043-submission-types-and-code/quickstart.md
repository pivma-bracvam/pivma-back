# Quickstart: validar a feature 043

## Pré-requisitos

- Docker em execução (Testcontainers para os testes).
- Dependências instaladas com `poetry install` (inclui `tzdata`).

## Testes

```bash
poe test tests/integration/journeys/etapa_1_submissao_triagem/test_submission_types_and_code.py
```

Esperado: as jornadas das duas histórias passam.

```bash
poe test
```

Esperado: suíte inteira verde, incluindo os testes ajustados pela remoção
da Prova de Conceito.

## Verificação manual pela API

Com o servidor de desenvolvimento no ar e uma sessão autenticada:

1. `GET /processes/templates` devolve os 4 tipos na ordem Método Novo,
   Método Novo – Dossiê Completo, Extensão do Domínio de Aplicação e Método
   Similar, com `sort.by = "display_order"`. Ver
   [contrato](contracts/process-templates.md).
2. `POST /processes` com `template_key: "pre_validated_method"` duas vezes:
   os códigos são `VAL-<ano>-0001` e `VAL-<ano>-0002` num banco novo.
3. `POST /processes` com `template_key: "proof_of_concept"` responde 404.

## Remoção completa

```bash
grep -rn "proof_of_concept" src tests manual README.md
```

Esperado: nenhuma ocorrência (SC-005). As specs em `specs/` continuam
citando o tipo, como histórico.

## Lint e documentação

```bash
poe lint
```

```bash
poe docs-build
```

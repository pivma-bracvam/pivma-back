# Quickstart: Validar a Regra "Todos os Campos Conformes"

Guia de validação executável para confirmar que a nova regra de consolidação
(`specs/026-all-fields-compliant-routing/spec.md`) está funcionando. Não repete
requisitos/entidades — ver `spec.md`, `data-model.md` e `contracts/consolidation-rule.md`.

## Pré-requisitos

- Ambiente de desenvolvimento configurado (`poetry install`), Postgres via
  Testcontainers disponível (padrão do projeto).
- `AI_PROVIDER` no modo fake/local (padrão em dev/test — nenhuma chamada real à
  OpenAI é necessária para validar a regra de consolidação).

## 1. Validação unitária da função pura (mais rápida)

A lógica inteira desta feature vive em `src/pivma/ai/consolidation.py`. Depois de
implementada a Decisão 2 do `research.md`:

```bash
poetry run pytest tests/unit/ai/test_consolidation.py -v
```

**Resultado esperado**: todos os testes passam, incluindo os casos reescritos que
prova a mudança de comportamento:
- um único critério `non_compliant` de severidade `low` → `result == 'negative'`
  (antes seria `'positive'`);
- um único critério `partial` (qualquer severidade) → `result == 'negative'`;
- um único critério `indeterminate` (qualquer severidade) → `result == 'negative'`;
- todos `compliant` → `result == 'positive'` (inalterado);
- lista vazia → `result == 'positive'` (inalterado, FR-006).

## 2. Validação de integração (roteamento fim a fim)

```bash
poetry run pytest tests/integration/ai/test_run_pre_evaluation.py -v
```

**Resultado esperado**: o cenário existente com severidade `critical` continua
roteando para `SUBMISSION` (negativo); o cenário com severidade `low` e enunciado
`COMPLIANT_STATEMENT` continua roteando para `TRIAGE` (positivo, porque o critério
é `compliant`, não porque a severidade é baixa). Adicionar (na task correspondente)
um novo cenário com severidade `low` e `NON_COMPLIANT_STATEMENT` — sob a regra
antiga isso permanecia positivo; sob a nova regra, deve rotear para `SUBMISSION`
(negativo). Esse é o teste que prova a mudança de comportamento fim a fim.

## 3. Validação manual via API real (`http://localhost:8000`)

Seguindo o padrão de demonstração já usado pela Spec 013 (`demos/`), sem criar
nada novo só para validar:

1. Como usuário BraCVAM/Admin, publicar uma avaliação com um critério de
   severidade **baixa** associado a um campo de texto do template de submissão
   (`POST /ai-evaluations`, `PATCH /ai-evaluations/{id}/versions/1`).
2. Como proponente, submeter o formulário com um valor que **não** satisfaça esse
   critério.
3. Consultar `GET /processes/{id}/pre-evaluation` após o processamento em segundo
   plano concluir.
4. **Esperado**: `consolidated_result == "negative"` e o processo retorna ao
   proponente (`status == "SUBMISSION"`), mesmo com severidade baixa —
   comportamento diferente do que a Spec 013 produzia antes desta feature.
5. Corrigir o campo e reenviar; **esperado**: novo `consolidated_result == "positive"`
   e o processo avança para `TRIAGE`.
6. (Opcional, cenário de indeterminado) Associar um critério a um alvo do tipo
   `document`; submeter com um documento anexado. **Esperado**: o critério conclui
   `indeterminate` (capacidade mockada) e `consolidated_result == "negative"` — o
   proponente vê as duas opções genéricas de sempre (corrigir/reenviar e
   intervenção direta), sem destaque especial para esse motivo (Clarification
   Session 2026-09-18, Q2).
7. Solicitar intervenção direta do BraCVAM nesse último caso e confirmar que o
   processo avança para `TRIAGE` preservando o relatório original com o critério
   indeterminado listado em `attention_points`.

## 4. Suíte completa (antes de considerar a feature concluída)

```bash
poetry run pytest
```

**Resultado esperado**: 100% verde, sem chamadas externas à OpenAI (FR de
observabilidade da Spec 013 preservado; `AI_PROVIDER` fake em `unit`/`api`/CI).

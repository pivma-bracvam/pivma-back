# Quickstart: validar a Spec 049

## Pré-requisitos

- Docker rodando: os testes sobem o PostgreSQL com pgvector via Testcontainers.
- Dependências instaladas (`poetry install`).

## Jornadas

| História | Teste | Resultado esperado |
|---|---|---|
| US1 | `tests/integration/journeys/etapa_1_submissao_triagem/test_proponent_triage_view.py` | Proponente vê a tarefa de triagem em `READY`, depois `COMPLETED`, e os eventos de decisão nos três desfechos, sem autor e sem `FIELD_REVIEWED`. |
| US2 | `tests/integration/journeys/etapa_1_submissao_triagem/test_proponent_reads_decided_reviews.py` | `reviews` vazio para o proponente antes da decisão e preenchido depois; o triador lê o rascunho. |
| US3 | `tests/integration/journeys/etapa_2_planejamento_preparacao/test_invite_timeline_privacy.py` | BraCVAM vê os eventos de convite com e-mail e autor; o proponente não vê nenhum; o convidado vê o próprio aceite. |
| US4 | `tests/integration/journeys/etapa_2_planejamento_preparacao/test_blind_reviewer_timeline.py` | Avaliador ad hoc não recebe o `user_id` do proponente nem de outro avaliador; o BraCVAM recebe todos os autores. |

## Testes focados

- Autorização: proponente recebe `403` em `/triage/reviews` e `/triage/decision` (`tests/api/routers/test_triage_proponent_view.py`).
- Regressão: com `triage.review`, autores e `FIELD_REVIEWED` continuam na linha do tempo (`test_triage_proponent_view.py`).
- Paginação: `total` desconta `FIELD_REVIEWED` (`test_triage_proponent_view.py`) e convites ocultos (`tests/api/routers/test_participant_timeline.py`).
- Isolamento: aceite do laboratório B fora da linha do tempo do laboratório A (`test_participant_timeline.py`).
- Cegamento: `tests/api/routers/test_timeline_blind_review.py` (ad hoc, revisor por pares, designação revogada, união de cargos).
- Pareceres: `tests/api/routers/test_activity_form_reviews.py` (rascunho, decididos, contestação da IA).
- Migração: `tests/integration/migrations/test_triage_proponent_view_migration.py` (upgrade inclui `proponent` uma vez; upgrade, downgrade e upgrade não duplicam; downgrade retira; o proponente passa no filtro de tarefas).
- Matriz da Fase 1: `tests/integration/database/test_activity_access_columns.py` com `proponent` em `view_roles` da triagem.

## Comandos

```bash
poetry run pytest tests/api/routers/test_triage_proponent_view.py tests/api/routers/test_participant_timeline.py tests/api/routers/test_timeline_blind_review.py tests/api/routers/test_activity_form_reviews.py tests/api/routers/test_timeline_router.py
```

```bash
poetry run pytest tests/integration/journeys/etapa_1_submissao_triagem tests/integration/journeys/etapa_2_planejamento_preparacao tests/integration/migrations/test_triage_proponent_view_migration.py tests/integration/database/test_activity_access_columns.py
```

```bash
poe lint && poe test && poe docs-build
```

Detalhes do que cada leitor recebe: [contracts/timeline-and-form.md](contracts/timeline-and-form.md) e [data-model.md](data-model.md).

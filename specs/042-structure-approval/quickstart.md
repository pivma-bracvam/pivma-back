# Quickstart: validar a homologação da estrutura

## Pré-requisitos

- Docker rodando (os testes usam Testcontainers com PostgreSQL 17).
- Dependências instaladas: `poetry install`.

## Verificações automáticas

```bash
poe lint
poe test                                   # suíte completa
pytest tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py -vv
poe docs-build                             # falha em link ou âncora quebrados
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

Resultado esperado: tudo verde. A jornada percorre a User Story 2 inteira
pela API pública.

## Roteiro manual pela API

Parta do tutorial [Montar a equipe e preparar as amostras](../../manual/tutorial/equipe-e-amostras.md)
com as dez atividades da Etapa 2 concluídas. O tutorial novo do manual traz
os comandos completos; aqui ficam só os resultados esperados.

1. `GET /processes/{id}/structure-approval` como BraCVAM: `status`
   `IN_PROGRESS`, dez pontos, `pending` vazio em todos.
2. `GET /tasks` como laboratório participante: nenhuma tarefa de
   recebimento.
3. `POST .../structure-approval/decision` com `REJECTED` e o ponto
   `assign_participating_laboratory`: `200`, `status` `BLOCKED`,
   `reopened` com `run_number` 2.
4. `GET /tasks` como Grupo Gestor: tarefa nova de "Definir os Laboratórios
   Participantes".
5. Grupo Gestor designa o laboratório certo e revoga o errado: o ponto
   continua em andamento. Ele declara a conclusão por
   `POST .../participants/roles/participating_laboratory/complete`. O ponto
   conclui e a homologação reabre com `run_number` 2; o painel aponta
   `laboratory_without_codes` e `codes_without_laboratory` no ponto das
   amostras.
6. `POST .../decision` com `APPROVED`: `409 structure_pending`.
7. Reprovar `sample_definition`; o Grupo de Seleção conclui as amostras de
   novo. A homologação volta a `IN_PROGRESS` com `run_number` 3.
8. `POST .../decision` com `APPROVED`: `200`, `status` `COMPLETED`.
9. `GET /tasks` como laboratório participante: tarefa de recebimento
   pronta.
10. `GET /processes/{id}/structure-approval`: três decisões no histórico, duas reprovações e a aprovação.

Contratos em [contracts/http-api.md](contracts/http-api.md); estados e
pendências em [data-model.md](data-model.md).

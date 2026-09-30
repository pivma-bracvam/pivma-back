# Quickstart: Validade da designação laboratorial

Guia de validação. Os detalhes de contrato estão em
[contracts/http-api.md](contracts/http-api.md) e os de dados em
[data-model.md](data-model.md).

## Pré-requisitos

- Python 3.14 e dependências: `poetry install`
- Docker em execução (os testes sobem `pgvector/pgvector:pg17` via
  testcontainers)

## Testes automatizados

```bash
poetry run pytest tests/api/routers/test_lab_designation_validity.py -q
poetry run pytest -q          # suíte completa (SC-005)
poetry run ruff check . && poetry run ruff format --check .
```

## Validação manual pela API

Com a API local (`alembic upgrade head` e servidor rodando), um Admin, um
processo em andamento do template 04 e o usuário `L` com vínculo ativo no
Laboratório A:

1. Designar `L` como `participating_laboratory` pelo Laboratório A
   (`POST /processes/{id}/participants`).
2. Autenticado como `L`, abrir uma atividade que concede ver a
   `participating_laboratory`. **Esperado**: `200`.
3. Como Admin, encerrar o vínculo:
   `DELETE /users/{L}/affiliations/{affiliation_id}`.
4. Como `L`, repetir o passo 2. **Esperado**: `404 not_found`. `GET /tasks`
   não lista as tarefas do cargo e `GET /processes` não lista o processo.
5. Como Admin, `GET /processes/{id}/participants`. **Esperado**: designação
   ativa com `effective: false`. `GET /processes/{id}/timeline` traz
   `PARTICIPANT_EFFECTIVENESS_LOST` com `reason: affiliation_ended`.
6. Como Admin, criar novo vínculo de `L` com o Laboratório A
   (`POST /users/{L}/affiliations`). **Esperado**: `L` volta a ver a
   atividade; a linha do tempo traz `PARTICIPANT_EFFECTIVENESS_RESTORED`.
7. Como Admin, `DELETE /institutions/{instituição do Laboratório A}`.
   **Esperado**: `L` perde o acesso de novo; o evento traz
   `reason: institution_deactivated`.
8. Repetir o passo 3 num processo encerrado. **Esperado**: acesso negado e
   nenhum evento novo na linha do tempo desse processo.

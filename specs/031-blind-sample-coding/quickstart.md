# Quickstart: validar a Spec 031

Guia de verificação ponta a ponta. Contrato em
[contracts/http-api.md](contracts/http-api.md); entidades em
[data-model.md](data-model.md).

## Pré-requisitos

- Docker (os testes sobem PostgreSQL com pgvector via testcontainers).
- Dependências instaladas: `poetry install` (inclui `segno`).

## Testes automatizados

```bash
poetry run pytest tests/unit/core/test_sample_service.py
poetry run pytest tests/api/routers/test_samples_router.py tests/api/routers/test_samples_access.py
poetry run pytest tests/integration/journeys/test_sample_definition_journey.py
poetry run pytest tests/integration/migrations/test_blind_sample_migration.py
poetry run pytest                     # suíte completa, sem regressão
poetry run ruff check . && poetry run ruff format --check .
```

## Roteiro manual (API local)

1. `docker compose up -d` e `poetry run alembic upgrade head`; o
   `entrypoint.sh` carrega os templates (novas versões).
2. Crie um processo de qualquer template (`POST /processes`), submeta a
   proposta e aprove a triagem como BraCVAM.
3. Como proponente, designe o Grupo Gestor. Como Grupo Gestor, designe um
   usuário em `sample_selection_group` e três usuários em
   `participating_laboratory`, cada um de um laboratório diferente.
4. `GET /tasks` com o usuário do Grupo de Seleção → aparece "Definição e
   Preparação das Amostras".
5. Cadastre 4 substâncias (`POST /processes/{id}/samples`) → cada resposta
   traz 3 códigos; `GET /processes/{id}/samples` mostra 12 códigos
   diferentes, sem prefixo comum por substância ou laboratório.
6. Tente cadastrar de novo o CAS `50-00-0` → **409** `duplicate_cas`. Tente
   `50-00-1` → **422**.
7. Anexe a SDS de 3 substâncias e tente concluir → **422** `missing_sds`.
   Anexe a quarta e conclua → **200**, `code_count: 12`.
8. `GET /processes/{id}/samples/labels` → 12 etiquetas; leia um `qr_svg` com
   o celular: a URL contém só o id do processo e o código.
9. `GET /processes/{id}/samples/vials/{code}` → código, lote e manuseio, sem
   nome químico nem CAS.
10. Repita os passos 5, 8 e 9 como laboratório participante e Grupo Gestor
    (**404**) e como admin e BraCVAM (**403**). Como admin,
    `GET /tasks?process_id={id}` mostra a tarefa "Definição e Preparação das
    Amostras" e seu status, sem conteúdo de amostras.
11. Após a conclusão, `POST`, `PATCH`, `DELETE` e `PUT .../sds` → **409**.
12. `GET /processes/{id}/timeline` como admin → eventos `SAMPLE_*` sem nome
    químico, CAS, lote nem código.

## Resultado esperado

Todos os comandos de teste passam; o roteiro manual reproduz os status
acima. Processos criados antes da feature continuam com as fases da versão
antiga do template.

# Guia de Validação: Exclusão (Soft-Delete) e Arquivamento de Processos

## Pré-requisitos

- PostgreSQL disponível pela configuração local do projeto.
- Dependências instaladas pelo Poetry ou `uv` conforme o ambiente.
- Migrações aplicadas e API iniciada.

```bash
docker compose up -d db
PYTHONPATH=src poetry run alembic upgrade head
PYTHONPATH=src poetry run fastapi dev src/pivma/__init__.py
```

Em outro terminal, carregar os usuários e a massa da demonstração:

```bash
uv run python -m scripts.seeds.seed_users
uv run python -m scripts.seeds.seed_process_retirement
```

## Verificação automatizada

Executar os testes diretamente relacionados e o lint após a implementação:

```bash
poetry run pytest -q tests/api/routers/test_process_retirement.py
poetry run pytest -q tests/unit/core/test_process_retirement.py tests/integration/database/test_process_retirement_deletion.py tests/integration/database/test_process_retirement_concurrency.py tests/integration/ai/test_process_retirement_pre_evaluation.py
poetry run ruff check src tests scripts/seeds
```

Os testes devem cobrir: soft-delete (nunca remoção física), preservação de anexos em disco, as duas vias de autorização de `DELETE` (proponente efetivo e Admin/BraCVAM), cascata seletiva de trabalho pendente, bloqueio de escrita após exclusão/arquivamento, listagem histórica de `ARCHIVED`, conclusão tardia de pré-avaliação e o filtro global de soft-delete (uma consulta comum não retorna um registro `AuditMixin` soft-deletado; `skip_soft_delete_filter=True` o retorna). Consulte [data-model.md](data-model.md) e o [contrato HTTP](contracts/process-lifecycle.openapi.yaml) para os resultados esperados.

## Validação ponta a ponta

1. Abra `http://localhost:8000/demos/` e selecione a demonstração de ciclo de vida.
2. Autentique como `proponent_user`, use `DELETE /processes/{own_id}` em um processo próprio não-terminal (pode já ter sido submetido) e confirme: `204 No Content`, o processo ausente de `GET /processes`, `status=CANCELLED` e `deleted_at` preenchidos ao consultar diretamente pelo bypass administrativo, e os arquivos ainda presentes em `ATTACHMENTS_DIR/{own_id}/` no disco.
3. Autentique como `admin` (perfil global `administrator` ou `bracvam`), use `DELETE /processes/{other_id}` em um processo de outro proponente e confirme que a operação é aceita, com o mesmo resultado do passo anterior.
4. Ainda como `admin`, use `PATCH /processes/{closed_id}/archive` em um processo `CLOSED` e em um processo já excluído (`CANCELLED` pelo passo 2 ou 3). Confirme que ambos passam a `ARCHIVED`, que a listagem padrão os omite e que `GET /processes?status=ARCHIVED` os retorna.
5. Tente `DELETE` em um processo já `ARCHIVED` ou já excluído, e `PATCH .../archive` em um processo ainda ativo; confirme `409` com `invalid_transition` e ausência de alterações em ambos os casos.
6. Dispare ou simule uma pré-avaliação pendente, exclua o processo antes de sua conclusão e confirme que a execução tardia não muda o status nem cria avanço de fluxo.

## Resultado esperado

Toda exclusão produz um evento de auditoria `PROCESS_DELETED` com autor, estado anterior e momento, sem remover processo, registros vinculados ou documentos armazenados. O arquivamento produz `PROCESS_ARCHIVED` nas mesmas condições da versão anterior desta feature. Nenhuma justificativa textual é exigida em nenhuma das duas operações.

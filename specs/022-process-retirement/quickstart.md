# Guia de Validação: Ciclo de Vida de Processos

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
poetry run pytest -q tests/unit/core/test_process_retirement.py tests/integration/database/test_process_retirement_deletion.py tests/integration/ai/test_process_retirement_pre_evaluation.py
poetry run ruff check src tests scripts/seeds
```

Os testes devem cobrir exclusão física de registros e anexos, transições, autorização, cascata seletiva, listagem histórica, bloqueio de escrita e conclusão tardia de pré-avaliação. Consulte [data-model.md](data-model.md) e o [contrato HTTP](contracts/process-lifecycle.openapi.yaml) para os resultados esperados.

## Validação ponta a ponta

1. Abra `http://localhost:8000/demos/` e selecione a demonstração de ciclo de vida.
2. Autentique como `proponent_user`, exclua o rascunho marcado pela demo com justificativa e confirme que processo, registros vinculados e diretório de anexos não permanecem disponíveis.
3. Autentique como `admin`, cancele o processo ativo, confirme a transição para `CANCELLED`, a indisponibilidade de tarefas/formulários para edição e o evento na linha do tempo.
4. Ainda como `admin`, arquive o processo `CLOSED` da massa. Confirme que a listagem padrão o omite e que `GET /processes?status=ARCHIVED` o retorna.
5. Tente arquivar o rascunho ou cancelar um processo já terminal e confirme `409` com `invalid_transition` e ausência de alterações.
6. Dispare ou simule uma pré-avaliação pendente, cancele o processo antes de sua conclusão e confirme que a execução tardia não muda o status nem cria avanço de fluxo.

## Resultado esperado

Cancelamento e arquivamento produzem um evento de auditoria com autor, justificativa e transição. A exclusão de rascunho remove fisicamente seu agregado e seus anexos.

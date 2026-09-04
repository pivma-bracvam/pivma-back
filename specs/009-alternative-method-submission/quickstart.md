# Guia de Validação: RF007

## Pré-requisitos

Use o ambiente descrito no [README](../../README.md): PostgreSQL em execução, migrações aplicadas e templates carregados.

```bash
docker compose up db -d
poetry run alembic upgrade head
poetry run python -m pivma.bootstrap_process_templates
```

Use duas contas autenticadas: proponente A e usuário B sem participação na instância de A.

## Cenário principal

1. Com A, crie um processo `full_validation` pelo contrato de [criação](contracts/submission-api.md#criar-submissão). Confirme `201`, `status: SUBMISSION` e `code` único.
2. Consulte o formulário inicial. Confirme que `fields` vem da definição persistida, em ordem, e que `values` começa vazio.
3. Salve `method_title`, `endpoint_target` e `expected_laboratories_count`. Consulte o formulário outra vez e confirme os valores.
4. Confirme que `is_submitted` continua `false` e a instância continua `SUBMISSION`. Não use o endpoint `POST` de envio formal.

## Validação de integridade

1. Envie uma chave inexistente junto de um valor válido. Confirme `422` com `field_key` da chave inexistente e ausência de alteração nos valores existentes.
2. Envie opção fora de `endpoint_target.options`, texto em campo integer, `false` em campo integer ou número fora de `min`/`max`. Confirme `422` por campo.
3. Envie `false` para campo booleano e `0` para campo numérico, quando definidos. Confirme que o backend os trata como valores, não como ausência.
4. Envie valor para `study_protocol_file`. Confirme `422` e ausência de `Artifact` ou valor simulado.

## Validação de autorização

1. Com B, tente listar processos, obter a instância de A, obter timeline, consultar o formulário, salvar rascunho e chamar o endpoint formal usando os UUIDs de A.
2. Confirme que a lista não contém a instância de A, sua contagem não a inclui e as demais chamadas retornam `404` sem valores, campos ou eventos.
3. Revogue a designação `proponent` de A. Repita leitura e gravação com A; confirme a mesma negação.
4. Dê a B uma designação ativa com outro papel. Confirme que a negação permanece.

## Testes automatizados previstos

Após implementar as tarefas, execute os testes focados e depois a suíte proporcional:

```bash
poetry run pytest tests/api/routers/test_process_router.py tests/api/routers/test_form_submission.py tests/integration/database/test_participant_authorization.py tests/integration/database/test_process_code_generation.py
poetry run ruff check src tests
```

O implementador deve conferir a saída de cada comando antes de relatar sucesso.

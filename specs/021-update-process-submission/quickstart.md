# Quickstart: 021 - Atualização de Instância de Submissão

## Pré-requisitos

```bash
poetry run python -m scripts.seeds.seed_users
poetry run python -m scripts.seeds.seed_submission_update
poetry run uvicorn pivma.app:app --port 8000
```

Use um token do proponente ou de um perfil BraCVAM/Admin efetivo. Os formatos
exatos e respostas estão em [contracts/process-submission.openapi.yaml](contracts/process-submission.openapi.yaml).

## Cenários de validação

1. Com um processo `SUBMISSION` em rascunho, faça `PUT /processes/{id}` com
   título e todos os campos não-arquivo. Confirme título, valores, template e
   `run_number` na resposta; estado, tarefa e run não mudam.
2. Faça `PATCH /processes/{id}` só com título e, depois, só com um valor.
   Confirme que valores omitidos permanecem intactos.
3. Envie campo desconhecido, valor inválido ou PUT incompleto. Espere 422 e
   confirme que nem título nem valores foram alterados.
4. Submeta formalmente o formulário. Repita PUT/PATCH e espere 409. Consulte
   a run submetida: título, valores e anexos do snapshot devem permanecer os
   mesmos.
5. Pela triagem, solicite `NEEDS_REVISION`; altere a run nova, reenvie e
   consulte `/submission-versions`. A versão anterior deve exibir a
   justificativa e o conteúdo congelado; a leitura padrão mostra a run atual.
6. Como usuário fora da visibilidade contextual, tente escrita e histórico;
   espere 404. Como processo fechado/cancelado, espere 409 para escrita.

## Testes automatizados

```bash
poetry run pytest tests/api/routers/test_process_submission_update.py -v
poetry run pytest tests/api/routers/test_form_submission.py tests/api/routers/test_form_attachments.py tests/api/routers/test_triage_decision.py -v
poetry run pytest tests/unit/core/test_process_engine.py -v
poetry run ruff check src tests
```

## Demonstração

Abra `http://localhost:8000/demos/submission-update/`. A página deve autenticar
o usuário, carregar o rascunho pela API real, permitir salvar pelos dois modos
e exibir payload/resposta. Ela não cria endpoints específicos de demo e pode
ser removida sem afetar `src/`.

# Quickstart: Processos de tipo aposentado na listagem e no detalhe

## Testes

```bash
poetry run pytest tests/integration/journeys/etapa_1_submissao_triagem/test_retired_type_process.py tests/api/routers/test_retired_template_processes.py
```

Resultado esperado: todos passam. Sem a correção, a jornada e os testes de lista
e detalhe falham com `AttributeError` em `_template_ref`.

## Preview

Depois do deploy, abra `GET /processes?page=1&per_page=100` logado. A resposta é
200 e os 3 processos de `proof_of_concept` aparecem com `template.key`,
`template.name` e `template.version`.

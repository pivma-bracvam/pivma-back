# Quickstart: Migração das listagens e referências resumidas

Guia de verificação. Contrato em [contracts/http-api.md](contracts/http-api.md); modelos em [data-model.md](data-model.md).

## Testes automatizados

```bash
poetry run pytest tests/unit/core/test_listing.py                  # helpers de paginação
poetry run pytest tests/integration/database/test_references.py    # carregamento em lote das referências
poetry run pytest tests/api/routers/test_listing_contract.py       # envelope e paginação nas 19 listagens
poetry run pytest tests/api/routers/test_references_openapi.py     # referências e logs fora do OpenAPI
poetry run pytest                                                  # suíte completa, sem regressão
poetry run ruff check . && poetry run ruff format --check .
```

Os nomes finais dos arquivos novos saem do `tasks.md`.

## Verificação manual (Swagger em `/docs`)

1. Abrir cada uma das 19 listagens do contrato: todas descrevem a resposta como envelope, com `page` e `per_page` e sem `offset`, `limit` ou `size`.
2. Procurar `/admin/logs`: não aparece.
3. Conferir os schemas `UserRef`, `ProfileRef`, `InstitutionRef`, `LaboratoryRef` e `TemplateRef`: todos os campos têm descrição.
4. Com um processo que tenha um laboratório participante, `GET /processes/{id}/participants`: cada item traz `user` com nome, e o laboratório traz `laboratory.institution`.
5. `GET /processes?per_page=1&page=2`: um item, `has_prev: true`.

Os resultados esperados vêm dos cenários de aceitação das US1 a US4 da spec.

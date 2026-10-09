# Quickstart: Template de coleta de dados

Roteiro para conferir a entrega de ponta a ponta. Os contratos estão em
[contracts/http-api.md](contracts/http-api.md) e as regras em
[data-model.md](data-model.md).

## Pré-requisitos

- Docker em execução (Testcontainers sobe o PostgreSQL dos testes).
- `poetry install` depois de incluir o `openpyxl`.

## Verificação automática

```bash
poetry run alembic upgrade head        # migração nova aplica sem erro
poe lint
poe test
poe docs-build
```

Os testes da feature ficam nos arquivos listados no `plan.md`. Para rodar só
eles:

```bash
poetry run pytest -k "collection_template" -vv
```

## Verificação manual pela API

Com `poe serve` e uma sessão de Admin ou BraCVAM (cookie de sessão e
cabeçalho `Origin` confiável nas escritas):

1. `POST /collection-templates` com nome, `min_experiments: 3` e
   `min_replicates: 2`. Esperado: 201, `columns: []`, `locked: false`.
2. Seis `POST /collection-templates/{id}/columns`, sem `position`, com os
   tipos `decimal`, `integer`, `date`, `text`, `select` (com opções) e
   `text`. Esperado: posições 1 a 6.
3. `GET /collection-templates/{id}/file?format=csv`. Esperado: o arquivo
   começa com os bytes `EF BB BF` e tem uma linha com nove nomes separados
   por `;`, começando por `codigo_amostra;experimento;replica`.
4. `GET /collection-templates/{id}/file?format=xlsx`. Esperado: ao abrir,
   uma planilha `resultados` com os nove cabeçalhos na linha 1.
5. `POST /collection-templates/{id}/columns` com a chave `replica`.
   Esperado: 409 `reserved_key`.
6. `POST /processes` com `collection_template_id` e um `template_key`
   válido. Esperado: 201 com o `collection_template_id` na resposta.
7. Leve o processo até a conclusão da definição das amostras, como no
   [guia de amostras cegas](../../manual/guias/definir-amostras-cegas.md).
   Depois, `GET /collection-templates/{id}`. Esperado: `locked: true`.
8. `POST /collection-templates/{id}/columns` com uma coluna nova. Esperado:
   409 `template_locked`. `PATCH` só com o nome: 200.
9. Com um usuário sem a permissão, `GET /collection-templates`: 403
   `forbidden`. `POST /processes` com `collection_template_id`: 403 e
   nenhum processo novo.

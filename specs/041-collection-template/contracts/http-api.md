# Contrato HTTP: Template de coleta de dados

Todas as rotas exigem sessão (`401 not_authenticated` sem ela) e a permissão
`collection_templates.manage` (`403 forbidden` sem ela). As escritas exigem
origem confiável (`403 invalid_origin`). Os corpos usam `extra='forbid'`, e
erros seguem a Spec 034. Mínimos e `position` vão de 1 a 2147483647, o
maior inteiro da coluna do banco. Os códigos de domínio estão em
[research R6](../research.md#r6-códigos-de-erro).

## Esquemas

`CollectionTemplateColumnPublic`

```json
{
  "id": "uuid",
  "key": "viabilidade",
  "label": "Viabilidade (%)",
  "type": "decimal",
  "required": true,
  "options": null,
  "position": 1
}
```

`CollectionTemplateSummary` (itens da listagem)

```json
{
  "id": "uuid",
  "name": "Ensaio de citotoxicidade",
  "description": "texto ou null",
  "min_experiments": 3,
  "min_replicates": 2,
  "locked": false,
  "created_by": "uuid", "created_at": "datetime",
  "updated_by": "uuid ou null", "updated_at": "datetime ou null"
}
```

`CollectionTemplatePublic` = `CollectionTemplateSummary` mais
`"columns": [CollectionTemplateColumnPublic]`, só as ativas, por `position`
crescente.

## Rotas

### `GET /collection-templates`

- Query: `page` (`>= 1`, padrão 1), `per_page` (1 a 100, padrão 20).
- 200: envelope paginado das Specs 032/033, com `data:
  [CollectionTemplateSummary]`, `filters_applied: {}` e `sort: {"by":
  "name", "order": "asc"}`. A ordem é o nome sem distinção de caixa e,
  depois, o `id`.

### `POST /collection-templates`

- Corpo:

  ```json
  {
    "name": "1..255",
    "description": "opcional",
    "min_experiments": 1,
    "min_replicates": 1
  }
  ```

- 201: `CollectionTemplatePublic`, com `columns: []` e `locked: false`.
- 422: `validation_error` (nome vazio ou longo, mínimo menor que 1 ou maior
  que 2147483647, campo desconhecido).

### `GET /collection-templates/{id}`

- 200: `CollectionTemplatePublic`.
- 404: `not_found`.

### `PATCH /collection-templates/{id}`

- Corpo: qualquer subconjunto de `name`, `description`, `min_experiments`,
  `min_replicates`, com as regras da criação. `name`, `min_experiments` e
  `min_replicates` não aceitam `null`.
- 200: `CollectionTemplatePublic`.
- 409: `template_locked`, se o template está travado e algum mínimo enviado
  difere do atual (research R3).
- 404, 422.

### `POST /collection-templates/{id}/columns`

- Corpo:

  ```json
  {
    "key": "^[a-z][a-z0-9_]{0,63}$",
    "label": "1..255",
    "type": "text | integer | decimal | date | select",
    "required": false,
    "options": ["1..255"],
    "position": 1
  }
  ```

  `required` (padrão `false`), `options` e `position` são opcionais.
- 201: `CollectionTemplateColumnPublic`.
- 409: `duplicate_key`, `reserved_key`, `position_taken`,
  `position_limit_reached`, `template_locked`. `position_limit_reached`
  ocorre sem `position`, quando a última coluna ativa já está em
  2147483647.
- 422: `invalid_options`, `validation_error`.
- 404: template inexistente.

### `PATCH /collection-templates/{id}/columns/{column_id}`

- Corpo: qualquer subconjunto dos campos da criação. `options` aceita `null`
  para remover as opções; os outros campos não aceitam `null`.
- 200: `CollectionTemplateColumnPublic`.
- Mesmos 409 e 422 da criação, exceto `position_limit_reached`, avaliados
  sobre o estado resultante, sem contar a própria coluna na unicidade.
- 404: template inexistente, coluna inexistente, excluída ou de outro
  template. O 404 vem antes do `template_locked`.

### `DELETE /collection-templates/{id}/columns/{column_id}`

- 204, sem corpo. A coluna recebe `deleted_at` e `deleted_by`.
- 409: `template_locked`.
- 404: como no `PATCH`.

### `GET /collection-templates/{id}/file?format=csv|xlsx`

- `format` obrigatório. Outro valor: 422 `validation_error`.
- 200 `csv`: `text/csv; charset=utf-8`, corpo em UTF-8 com BOM, separador
  `;`, uma linha:
  `codigo_amostra;experimento;replica;<chaves por position>`.
- 200 `xlsx`:
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, uma
  planilha `resultados` com o mesmo cabeçalho na linha 1 e nada mais.
- Cabeçalho `Content-Disposition: attachment;
  filename="template-coleta-<id>.<csv|xlsx>"`.
- 404: template inexistente.

## Rotas existentes alteradas

### `POST /processes`

- Como as demais escritas de `/processes`, exige origem confiável com
  cookie (`403 invalid_origin`, research R11).
- Corpo ganha `collection_template_id` (UUID, opcional).
- Ordem das recusas (research R10):
  1. campo presente sem `collection_templates.manage`: 403 `forbidden`;
  2. `template_key` inexistente: o 404 atual;
  3. template de coleta inexistente: 404 `not_found`.
- 201: `ProcessInstanceDetail` com `collection_template_id`.

### `GET /processes` e `GET /processes/{id}`

- `ProcessInstanceDetail` ganha `collection_template_id` (UUID ou `null`).

### Evento `PROCESS_CREATED`

- `context_data` ganha `collection_template_id` quando o processo nasce com
  o vínculo.

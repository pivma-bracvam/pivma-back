# Data Model: Template de coleta de dados

Uma migração Alembic (`down_revision = 'b7c3e1f2a9d4'`) cria as duas tabelas,
acrescenta o vínculo em `process_instances` e insere a permissão (research
R9). As duas tabelas novas herdam o `AuditMixin`.

## `collection_templates` (`CollectionTemplate`)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `id` | UUID, PK | gerado |
| `name` | `String(255)` | obrigatório, 1 a 255 caracteres, não único |
| `description` | `Text`, nulo | opcional |
| `min_experiments` | `Integer` | `>= 1` e `<= 2147483647` (check `ck_collection_templates_min_experiments`) |
| `min_replicates` | `Integer` | `>= 1` e `<= 2147483647` (check `ck_collection_templates_min_replicates`) |
| `AuditMixin` | | `created_*`, `updated_*`, `deleted_*` |

- Nenhuma rota exclui o template (FR-030). `deleted_at` fica sempre nulo
  nesta entrega.
- **Estado derivado `locked`**: verdadeiro se existe processo com
  `collection_template_id = id` e a `ActivityInstance` `sample_definition`
  desse processo está `COMPLETED`, contando os processos excluídos (research
  R2). Não fica gravado.
- As colunas ativas vêm de uma consulta por `collection_template_id`
  ordenada por `position`, sem relação ORM.

## `collection_template_columns` (`CollectionTemplateColumn`)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `id` | UUID, PK | gerado |
| `collection_template_id` | UUID, FK `collection_templates.id` | obrigatório |
| `label` | `String(255)` | obrigatório, 1 a 255 caracteres |
| `key` | `String(64)` | `^[a-z][a-z0-9_]{0,63}$`; fora de `codigo_amostra`, `experimento`, `replica` |
| `column_type` | `String(16)` | `text`, `integer`, `decimal`, `date` ou `select` (check `ck_collection_template_columns_type`) |
| `required` | `Boolean` | padrão `false` |
| `options` | `JSONB`, nulo | lista de textos; obrigatória e não vazia em `select`, nula nos demais |
| `position` | `Integer` | `>= 1` e `<= 2147483647` (check `ck_collection_template_columns_position`) |
| `AuditMixin` | | a exclusão é lógica (`deleted_at`, `deleted_by`) |

Índices:

- `uq_collection_template_columns_key_active`: único em
  `(collection_template_id, key)` onde `deleted_at IS NULL`.
- `uq_collection_template_columns_position_active`: único em
  `(collection_template_id, position)` onde `deleted_at IS NULL`.

Regras do serviço, conferidas sob a trava da linha do template (research R4
e R5):

- Chave única entre as colunas ativas (`duplicate_key`) e fora das
  reservadas (`reserved_key`).
- Posição única entre as ativas (`position_taken`). Sem posição, recebe a
  maior posição ativa mais 1, ou 1; acima de 2147483647,
  `position_limit_reached`.
- `select` exige ao menos uma opção. Os outros tipos exigem `options` nulo.
  Opção repetida também gera `invalid_options`; opção vazia ou com mais de
  255 caracteres cai na validação de entrada. No `PATCH`, a regra vale para
  o estado resultante.
- Nenhuma escrita com o template travado (`template_locked`). Coluna
  inexistente responde 404 antes dessa checagem.

## `process_instances` (existente)

| Coluna nova | Tipo | Regra |
| --- | --- | --- |
| `collection_template_id` | UUID, FK `collection_templates.id`, nulo | gravado só na criação; índice `ix_process_instances_collection_template_id` |

O índice atende à consulta de travamento.

## Constantes no código

- `RESERVED_COLUMN_KEYS = ('codigo_amostra', 'experimento', 'replica')`, na
  ordem do cabeçalho.
- `COLUMN_TYPES = ('text', 'integer', 'decimal', 'date', 'select')`.
- `COLLECTION_TEMPLATES_MANAGE = 'collection_templates.manage'`.

## Permissão

| `id` | `code` | `description` |
| --- | --- | --- |
| `00000000-0000-0000-0000-00000000010e` | `collection_templates.manage` | Gerir o catálogo de templates de coleta de dados (colunas, mínimos e arquivo-modelo). |

## Evento alterado

`PROCESS_CREATED.context_data` ganha `collection_template_id` (texto do UUID)
quando o processo é criado com o vínculo. Sem vínculo, o evento fica igual.

## Transições

O template não tem estados gravados. A única transição é derivada:
`locked = false` → `locked = true` quando a definição das amostras de um
processo vinculado conclui. Ela não volta, porque a definição das amostras
não reabre (Spec 031) e o cálculo conta processos excluídos.

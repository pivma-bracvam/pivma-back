# Data Model: Terminologia dos tipos e código da submissão

Uma migração Alembic, a partir da head `a3d5f7b9c1e2`.

## `process_templates` (alterada)

| Coluna | Tipo | Regra |
|---|---|---|
| `display_order` | `INTEGER NULL` | Vem de `process_template.display_order` no YAML. Obrigatória e maior ou igual a 1 nos YAMLs (R2). Nula só em templates criados direto no banco. |

Valores nos YAMLs:

| Chave | `display_order` | Nome |
|---|---|---|
| `pre_validated_method` | 1 | Método Novo |
| `validated_method_dossier` | 2 | Método Novo – Dossiê Completo |
| `scope_extension` | 3 | Extensão do Domínio de Aplicação |
| `me_too_validation` | 4 | Método Similar |

As descrições são as da tabela de Clarifications da spec.

## `process_code_sequences` (nova)

| Coluna | Tipo | Regra |
|---|---|---|
| `year` | `INTEGER` PK | Ano da criação no horário de Brasília. |
| `last_value` | `INTEGER NOT NULL` | Último número usado no ano. Começa em 1 na primeira criação do ano. |
| colunas do `AuditMixin` | | `created_by`: quem criou o primeiro processo do ano. `updated_at` e `updated_by`: o último incremento e quem criou esse processo. |

Incremento: upsert com `ON CONFLICT (year) DO UPDATE … RETURNING`, na
transação da criação do processo (R3). Sem rota, sem leitura fora de
`generate_process_code`.

## `process_instances.code` (sem mudança de esquema)

Formato novo `VAL-<ano>-<n:04d>`. A restrição única existente continua.
Códigos antigos ficam como estão.

## `form_templates` (dados)

O registro `submission_proof_of_concept_v1` recebe soft delete no bootstrap,
junto com o template de processo `proof_of_concept`. Os nomes dos quatro
formulários de submissão mudam (research R7).

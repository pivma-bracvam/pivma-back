# Data Model: Definição e Preparação das Amostras

Duas tabelas novas, uma setting nova e mudanças nos YAMLs de template. Todas
as tabelas usam `AuditMixin` (criação, atualização e exclusão lógica).

## StudySubstance (`study_substances`)

Substância cadastrada num processo pelo Grupo de Seleção de Amostras.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `process_instance_id` | UUID | FK `process_instances.id`, obrigatório |
| `chemical_name` | String(255) | obrigatório, sem espaços nas pontas, não vazio |
| `cas_number` | String(12) | obrigatório; formato `^\d{2,7}-\d{2}-\d$` e dígito verificador válido (FR-006) |
| `lot` | String(64) | obrigatório |
| `purity` | String(64) | opcional, texto livre (ex.: `≥ 99%`) |
| `solubility` | Text | opcional |
| `safe_handling_instructions` | Text | obrigatório (perigos, EPI, primeiros socorros) |
| `sds_artifact_id` | UUID \| null | FK `artifacts.id`; obrigatório só para concluir (FR-014) |

**Índices**

- `uq_study_substances_process_cas_active`: único em
  `(process_instance_id, cas_number)` onde `deleted_at IS NULL` (FR-005).

**Dígito verificador do CAS**: com os dígitos antes do último lidos da
direita para a esquerda com pesos 1, 2, 3, …, a soma ponderada módulo 10
deve igualar o último dígito. Ex.: `50-00-0` → 0×1 + 0×2 + 0×3 + 5×4 = 20 →
0 ✓.

## BlindSampleCode (`blind_sample_codes`)

Um frasco: a combinação substância × laboratório com seu código opaco.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `process_instance_id` | UUID | FK `process_instances.id` (denormalizado para o índice de unicidade) |
| `substance_id` | UUID | FK `study_substances.id` |
| `laboratory_id` | UUID | FK `laboratories.id` |
| `code` | String(8) | 8 caracteres de `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (R5) |

**Índices**

- `uq_blind_sample_codes_process_code_active`: único em
  `(process_instance_id, code)` onde `deleted_at IS NULL` (FR-011).
- `uq_blind_sample_codes_substance_lab_active`: único em
  `(substance_id, laboratory_id)` onde `deleted_at IS NULL` (FR-012).

**Ciclo de vida**

- Criado ao cadastrar a substância (um por laboratório ativo, R4) e na
  conclusão para combinações faltantes (FR-010, FR-013).
- Excluído logicamente ao remover a substância (FR-008) ou, na conclusão,
  quando o laboratório não tem mais designação ativa (FR-013).
- Alterar a substância não mexe nos códigos (FR-008).

## Artifact (existente)

A SDS usa `Artifact` com `key='sample_sds'`, `activity_run_id` da execução
aberta de `sample_definition`, `status='SUBMITTED'` e
`metadata_payload={'original_filename', 'extension', 'substance_id'}`.
Substituir a SDS exclui logicamente o artefato anterior e remove o arquivo
(R7).

## ActivityInstance `sample_definition` (existente, sem coluna nova)

| Status | Significado para amostras |
|---|---|
| `BLOCKED` | falta concluir a atribuição do Grupo de Seleção ou dos laboratórios participantes; toda rota de amostras responde 409 nas mutações e lista vazia nas leituras |
| `IN_PROGRESS` | cadastro aberto: cadastrar, alterar, remover, anexar, concluir |
| `COMPLETED` | conjunto congelado: só leituras (lista, etiquetas, SDS, rota do frasco) |

`view_roles = ['admin', 'bracvam', 'sample_selection_group']`,
`edit_roles = ['sample_selection_group']` (resultado de
`resolve_activity_access` para o YAML de R1).

## Settings

- `SAMPLE_QR_BASE_URL: str | None = None` — base da URL do frontend gravada
  no QR code. Sem valor, usa a primeira origem de `AUTH_ALLOWED_ORIGINS` (R8).

## Templates (YAML)

| Template | Versão | Mudança |
|---|---|---|
| `01_pre_validated_method.yaml` | 2 → 3 | + Fase 2 do template 04 + `sample_definition` |
| `02_scope_extension.yaml` | 2 → 3 | idem |
| `03_me_too_validation.yaml` | 2 → 3 | idem |
| `04_validated_method_dossier.yaml` | 4 → 5 | + `sample_definition` na Fase 2 |
| `05_proof_of_concept.yaml` | 2 → 3 | + Fase 2 do template 04 + `sample_definition` |

## Migração

Uma revisão Alembic nova (`down_revision = '7e21b4c0a9d3'`) cria as duas
tabelas e os três índices parciais; o downgrade os remove. Não há migração
de dados: processos existentes continuam em suas versões de template.

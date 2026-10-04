# Data Model: Spec 040

Todas as tabelas novas herdam `AuditMixin` (criação, alteração, exclusão
lógica). Uma migração Alembic, depois de `6fe19f1c95e9`.

## `study_substances` (ampliada)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `reference_classification` | `Text` nulo | obrigatória na criação (FR-001); só Grupo de Seleção lê |
| `storage_temperature_regime` | `String(16)` nulo | `ambient`, `refrigerated`, `frozen`, `deep_frozen`, `custom` |
| `storage_temperature_min` | `Float` nulo | °C |
| `storage_temperature_max` | `Float` nulo | °C; `min <= max` |
| `vial_nominal_quantity` | `Float` nulo | > 0 |
| `vial_unit` | `String(16)` nulo | ex.: `mL`, `g` |
| `packaging_type` | `String(255)` nulo | |
| `expiration_date` | `Date` nulo | |
| `reserve_vials_count` | `Integer` não nulo, padrão 0 | ≥ 0; debitada no reenvio |
| `ghs_hazard_pictograms` | `ARRAY(String(5))` não nulo, padrão `{}` | `GHS01`…`GHS09`, sem repetição |

Regime e faixa (FR-003 a FR-005): faixa sem regime → recusada; `ambient` sem
faixa → 15/25; `refrigerated` sem faixa → 2/8; `frozen`, `deep_frozen`,
`custom` → mínimo e máximo obrigatórios.

## `blind_sample_codes` (ampliada)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `replaces_code_id` | FK `blind_sample_codes.id` nula | código que este substitui (reenvio) |

## `sample_receipts` (nova)

Registro de recebimento de um frasco.

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `id` | UUID PK | |
| `process_instance_id` | FK | |
| `activity_run_id` | FK `activity_runs` | execução do laboratório em que foi registrado |
| `blind_sample_code_id` | FK `blind_sample_codes` | único entre registros ativos |
| `laboratory_id` | FK `laboratories` | laboratório do código |
| `opened_at` | `DateTime` | não futuro |
| `temperature_celsius` | `Float` | |
| `package_state` | `String(16)` | `intact`, `damaged`, `violated` |
| `notes` | `Text` nulo | |
| `conforming` | `Boolean` | FR-024 |
| `deviations` | `ARRAY(String(32))` | `temperature_out_of_range`, `package_damaged`, `package_violated` |

Índice: `uq_sample_receipts_code_active (blind_sample_code_id) WHERE deleted_at IS NULL`.

## `sample_receipt_nonconformities` (nova)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `id` | UUID PK | |
| `process_instance_id` | FK | |
| `receipt_id` | FK `sample_receipts`, único | uma por registro fora de ordem |
| `laboratory_id` | FK `laboratories` | |
| `status` | `String(16)` | `OPEN` → `RESOLVED` |
| `decision` | `String(32)` nulo | `accept_with_caveat`, `resend`, `disqualify` |
| `justification` | `Text` nulo | não vazia na decisão |
| `decided_by` | FK `users` nula | |
| `decided_at` | `DateTime` nulo | |
| `replacement_code_id` | FK `blind_sample_codes` nula | código novo, na decisão `resend` |

Índice: `ix_sample_receipt_nonconformities_process_status (process_instance_id, status)`.

## Fotos

`artifacts` existente: `key = 'sample_receipt_photo'`, `activity_run_id` =
execução do laboratório, `metadata_payload = {receipt_id, original_filename,
extension}`.

## Situação do frasco (derivada, FR-037)

```text
código ativo sem registro                          → pending
registro em ordem                                  → received
inconformidade OPEN                                → awaiting_decision
inconformidade RESOLVED, accept_with_caveat        → accepted_with_caveat
inconformidade RESOLVED, resend                    → replaced
inconformidade RESOLVED, disqualify                → disqualified
```

O laboratório vê os códigos ativos do laboratório e os excluídos que têm
registro (frasco substituído).

## Lote completo (FR-025)

Todo código **ativo** do laboratório tem registro com `conforming = true` ou
inconformidade resolvida com `accept_with_caveat`.

## Transições da execução do laboratório em `sample_receipt`

```text
BLOCKED → IN_PROGRESS   (definição das amostras concluída; Spec 036)
IN_PROGRESS → COMPLETED (lote completo: no registro ou no aceite com ressalva)
IN_PROGRESS → WAIVED    (desclassificação ou dispensa pelo gestor)
```

## Execução de `sample_receipt_resolution`

```text
(sem execução aberta) → IN_PROGRESS  ao abrir a primeira inconformidade
IN_PROGRESS → COMPLETED               quando não resta inconformidade OPEN no processo
```

# Contract — Associação de Avaliações a Alvos de Formulário

Router: `src/pivma/routers/ai_evaluations.py` (mesmo módulo) · Prefixo `/form-templates`.

Autorização: `ai_evaluations.manage` + `TrustedOrigin` para mutação; `ai_evaluations.read` para leitura. Consistente com a Spec 012 (edição de template restrita ao BraCVAM).

Estes endpoints são o back-end **compartilhado** pelos dois módulos de demonstração (editor de formulário e biblioteca). Nenhum endpoint dedicado a demo.

---

### `GET /form-templates/{template_key}/evaluation-assignments`
`200` →
```json
{ "template_key": "pre_validated_method", "assignments": [
  { "id": "...", "definition_id": "...", "definition_name": "Verificação de estrutura de POP",
    "pinned_version_id": null, "effective_version_number": 2,
    "target_type": "field", "field_keys": ["standard_operating_procedure"], "enabled": true }
] }
```
`404` se o template não existe.

### `PUT /form-templates/{template_key}/evaluation-assignments`
Substitui a lista completa de associações do template (semântica de "set", como o editor de campos da Spec 012).
Body:
```json
{ "assignments": [
  { "definition_id": "...", "pinned_version_id": null,
    "target_type": "field", "field_keys": ["standard_operating_procedure"], "enabled": true },
  { "definition_id": "...", "target_type": "field_set",
    "field_keys": ["method_summary", "standard_operating_procedure"] }
] }
```
Validações:
- `definition_id` deve existir e ter ≥1 versão **publicada** (senão `422`).
- `field_keys` devem existir no template para `target_type ∈ {field, field_set}` (senão `422`).
- `field_keys` deve ser vazio para `target_type ∈ {form, process}`.
- `pinned_version_id` (quando presente) deve pertencer à `definition_id` e estar `published`.
`200` → lista efetiva após a substituição. `403` para perfil não-BraCVAM.

### `GET /form-templates/{template_key}/evaluable-fields`
Auxiliar de UI (domínio, não facilitador): lista os campos do template com `ai_evaluation_enabled=true` e as definições já associadas a cada um.
`200` → `{ "fields": [ { "field_key": "...", "label": "...", "assignments": [ {definition_id, definition_name} ] } ] }`

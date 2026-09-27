# Contrato HTTP: Definição e Preparação das Amostras

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **compatível**: só rotas novas. As rotas de template mudam de
conteúdo (novas versões com Fase 2), não de formato. Legenda: 🟢 novo,
🟡 muda conteúdo.

## Regra de acesso comum

Toda rota abaixo exige a concessão de **edição** na atividade
`sample_definition` do processo (research R3):

| Quem | Resposta |
|---|---|
| Grupo de Seleção de Amostras do processo | acesso |
| Admin, BraCVAM (veem a atividade, não editam) | **403** |
| Laboratório participante, laboratório líder, Grupo Gestor, demais participantes, outro processo | **404** |
| Sem login | **401** |
| Membro do Grupo com conflito de interesse vigente | **403** |

Rotas de mutação também exigem origem confiável (`TrustedOrigin`), como as
demais mutações da API.

## Tipos

```json
// SampleSubstance
{
  "id": "uuid",
  "chemical_name": "Formaldeído",
  "cas_number": "50-00-0",
  "lot": "L-2026-04",
  "purity": "≥ 37%",
  "solubility": "Miscível em água",
  "safe_handling_instructions": "Tóxico por inalação. Usar luvas nitrílicas...",
  "sds": { "filename": "sds.pdf", "size": 182044, "uploaded_at": "2026-09-26T12:00:00Z" },  // null sem SDS
  "blind_codes": [
    { "code": "K7Q2M9XD", "laboratory_id": "uuid", "laboratory_name": "Lab A" }
  ]
}

// SampleLabel
{
  "code": "K7Q2M9XD",
  "study_code": "VAL-2026-3f9a1c2b7e4d5a60",
  "laboratory_id": "uuid",
  "laboratory_name": "Lab A",
  "lot": "L-2026-04",
  "qr_url": "https://front.exemplo/amostras/<process_id>/frascos/K7Q2M9XD",
  "qr_svg": "data:image/svg+xml;base64,PHN2Zy..."
}

// BlindVial (visão cega; nunca nome químico, CAS nem SDS)
{
  "code": "K7Q2M9XD",
  "lot": "L-2026-04",
  "safe_handling_instructions": "Tóxico por inalação. Usar luvas nitrílicas..."
}
```

## Rotas

Prefixo `/processes/{id}/samples`.

| Endpoint | Sucesso | Erros específicos |
|---|---|---|
| 🟢 `GET /processes/{id}/samples` | **200** `{ "activity_status": "BLOCKED \| IN_PROGRESS \| COMPLETED", "substances": SampleSubstance[] }`, ordenado por `created_at`, `id` | — |
| 🟢 `POST /processes/{id}/samples` | **201** `SampleSubstance` com um código por laboratório ativo (pode ser `[]` sem laboratório) | **422** campo obrigatório ausente, CAS com formato ou dígito inválido; **409** `code=duplicate_cas`; **409** `code=invalid_transition` atividade fora de `IN_PROGRESS` ou processo fora de `OPEN` |
| 🟢 `PATCH /processes/{id}/samples/{substance_id}` | **200** `SampleSubstance` (códigos inalterados) | **404** substância de outro processo ou removida; **422**; **409** `duplicate_cas`; **409** `invalid_transition` |
| 🟢 `DELETE /processes/{id}/samples/{substance_id}` | **204** (substância, códigos e SDS excluídos logicamente) | **404**; **409** `invalid_transition` |
| 🟢 `PUT /processes/{id}/samples/{substance_id}/sds` (multipart `file`) | **200** `SampleSubstance` | **422** `extension_not_allowed` (não PDF); **400** `empty_file`; **413** `file_too_large`; **404**; **409** `invalid_transition` |
| 🟢 `GET /processes/{id}/samples/{substance_id}/sds` | **200** PDF (`application/pdf`, `Content-Disposition` com o nome original) | **404** sem SDS |
| 🟢 `POST /processes/{id}/samples/complete` | **200** `{ "activity_status": "COMPLETED", "substance_count": 4, "laboratory_count": 3, "code_count": 12 }` | **422** `code=no_substances`, `code=missing_sds` (com `substance_ids`), `code=no_laboratories`; **409** `invalid_transition` |
| 🟢 `GET /processes/{id}/samples/labels` | **200** `SampleLabel[]`, ordenado por laboratório e código | — |
| 🟢 `GET /processes/{id}/samples/vials/{code}` | **200** `BlindVial` | **404** código inexistente no processo |

Os status de erro seguem os códigos já usados pela API de anexos
(`_ATTACHMENT_ERROR_STATUS` em `routers/forms.py`) e pela Spec 030
(`invalid_transition`).

## Rotas existentes com conteúdo novo

| Endpoint | Mudança |
|---|---|
| 🟡 `GET /processes/templates/{key}` | as novas versões trazem `phase_2_role_assignment` em todos os templates e a atividade `sample_definition` (`activity_type: "sample_definition"`) |
| 🟡 `GET /tasks` | o Grupo de Seleção recebe a tarefa "Definição e Preparação das Amostras" quando a atividade abre; admin e BraCVAM também a veem (concessão de ver), que é como acompanham o status sem acessar o conteúdo (FR-023) |
| 🟡 `GET /processes/{id}/timeline` | novos `event_type` `SAMPLE_*` (research R9), com `context_data` só com ids e contagens |

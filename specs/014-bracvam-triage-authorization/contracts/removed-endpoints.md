# Contrato — O que sai da API (remoção da Spec 010)

## Endpoint removido

### `POST /forms/instances/{instance_id}/evaluate-ai`
- Router: `forms.direct_forms_router` (`prefix='/forms'`, tag `Forms AI`).
- Disparava `FormAIPipelineEngine.run_field_pipeline` sobre cada campo com
  `ai_evaluation_enabled`, gravava `artifact.metadata_payload['ai_evaluation']`.
- **Depois**: rota inexistente → **404** para qualquer método.
- `src/pivma/__init__.py`: remover `app.include_router(forms.direct_forms_router)`.

## Módulos removidos (exclusão física)

| Caminho | Conteúdo |
|---|---|
| `src/pivma/ai/pipeline.py` | `FormAIPipelineEngine` |
| `src/pivma/ai/steps/` | `context_extraction.py`, `mock_evaluation.py`, `verdict_synthesis.py`, `__init__.py` |

## Símbolos removidos de `src/pivma/ai/contracts.py`

- `AIEvaluationVerdict`
- `PipelineContext` (dataclass da engine legada)
- `StepResult` (dataclass da engine legada)
- `PipelineExecutionGroup.verdict` (campo) e o default
  `pipeline_name = 'form_ai_field_evaluation'`

**Mantidos** (compartilhados com a Spec 013): `AIStepExecutionLog`,
`OperationalEventIndex`, `PipelineExecutionGroup` (sem `verdict`),
`OperationalEventIndex`.

## Código de domínio ajustado

| Arquivo | Mudança |
|---|---|
| `src/pivma/core/process_engine.py` | remover `_run_legacy_field_ai_mock` e imports `FormAIPipelineEngine`/`PipelineContext`; o ramo `else` de `submit_proposal_form` vira `_unblock_triage_activity` + `status='TRIAGE'` + audit (D9) |
| `src/pivma/routers/forms.py` | remover `direct_forms_router` e a rota; em `get_activity_form`, remover a leitura de `metadata_payload['ai_evaluation']` e do artefato `key == 'ai_evaluation_report'`; parar de passar `ai_evaluation=` |
| `src/pivma/core/log_service.py` | remover import e uso de `AIEvaluationVerdict`; `_build_pipeline_group` deixa de extrair `verdict` |
| `src/pivma/schemas.py` | `ActivityCompletionResponse.ai_evaluation` e `FormInstanceResponse.ai_evaluation` removidos |

## Testes removidos

- `tests/unit/test_ai_pipeline.py`
- `tests/integration/test_form_ai_evaluation_api.py`

## Testes ajustados

- `tests/api/routers/test_form_submission.py` — não esperar `ai_evaluation` na
  resposta; formulário sem avaliações → `status TRIAGE`, sem artefato de parecer.
- Qualquer teste que valide o payload de `get_activity_form` com `ai_evaluation`.

## Dados históricos

`artifact.metadata_payload['ai_evaluation']` e artefatos
`key == 'ai_evaluation_report'` de processos antigos **permanecem** no banco
(Princípio V) — apenas deixam de ser expostos e nenhum novo é criado.

## Spec 013 — atualizar

- `spec.md`: FR-022 ("motor de pipeline único") deixa de ter débito; nota de que
  a esteira legada foi removida na Spec 014.
- `tasks.md`: T041 (repontar/remover o endpoint) → concluído pela Spec 014.
- `/speckit-analyze` L1 → fechado.

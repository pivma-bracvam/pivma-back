---

description: "Task list for Anexos de Arquivo em Formulários (Spec 016)"
---

# Tasks: Anexos de Arquivo em Formulários

**Input**: Design documents from `/specs/016-form-attachments/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/form-attachments.md, quickstart.md

**Tests**: INCLUÍDOS. A constituição (Princípio IV, "NÃO NEGOCIÁVEL") exige testes
nas 4 camadas e a skill `fastapi-testing-methodology` ao criar/alterar testes.

**Organization**: Tarefas agrupadas por user story (spec.md) para implementação e
teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependências pendentes)
- **[Story]**: US1..US4 conforme spec.md

## Path Conventions

Backend único: `src/pivma/`, `tests/` na raiz do repositório (conforme plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: preparar ambiente, dependências e configuração

- [ ] T001 Criar a git worktree da feature: `git worktree add -b 016-form-attachments ../pivma-back-016-form-attachments develop` (a partir de `develop`, estado atual) e passar a trabalhar em `../pivma-back-016-form-attachments`
- [ ] T002 [P] Promover `python-multipart` a dependência direta em `pyproject.toml` (bloco de dependências do projeto, hoje só transitiva em `uv.lock`) e rodar `uv sync`
- [ ] T003 [P] Adicionar `var/attachments/` ao `.gitignore` na raiz do repositório
- [ ] T004 Adicionar as chaves de anexo em `src/pivma/core/settings.py` na classe `Settings`: `ATTACHMENTS_DIR: str = Field(default='var/attachments')`, `ATTACHMENT_MAX_SIZE_MB: int = Field(default=25)`, `ATTACHMENT_DEFAULT_EXTENSIONS: list[str] = Field(default_factory=lambda: ['pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'])` (leitura só via `Settings` — proibido env ad hoc)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: núcleo compartilhado por todas as user stories

**⚠️ CRITICAL**: nenhuma user story começa antes desta fase

- [ ] T005 Criar `src/pivma/core/attachment_service.py` com helpers puros: `resolve_allowed_extensions(field, settings) -> set[str]` (usa `field.validation_rules['allowed_extensions']` quando presente, senão `settings.ATTACHMENT_DEFAULT_EXTENSIONS`); `resolve_max_bytes(field, settings) -> int` (`field.validation_rules['max_size_mb']` senão `settings.ATTACHMENT_MAX_SIZE_MB`, × 1024²); `validate_filename(name, allowed) -> tuple[str, str | None]` (extensão minúscula sem ponto; erro `extension_not_allowed`); `attachment_relpath(process_id, artifact_id, ext) -> str` (`f'{process_id}/{artifact_id}.{ext}'`); `store_stream(upload, dest_path, max_bytes) -> tuple[int, str]` (grava em blocos, aborta com `file_too_large` ao exceder `max_bytes`, remove arquivo parcial, erro `empty_file` se 0 byte, retorna `(size, sha256_hexdigest)`); `remove_file_best_effort(abs_path) -> None`
- [ ] T006 [P] Adicionar schemas em `src/pivma/schemas.py`: `AttachmentMetadata` (`artifact_id: UUID`, `filename: str`, `size: int`, `mime_type: str | None`, `extension: str`, `checksum_sha256: str`, `uploaded_at: datetime`); `AttachmentUploadResponse` (`field_key: str`, `attachment: AttachmentMetadata`, `replaced_previous: bool`); `AttachmentRemovedResponse` (`field_key: str`, `removed: bool`); e adicionar `attachment: AttachmentMetadata | None = None` em `FormFieldDefinition`
- [ ] T007 [P] Adicionar em `src/pivma/routers/forms.py` o helper `_attachment_metadata(artifact) -> AttachmentMetadata` construindo a partir de `Artifact` (`name`, `file_size`, `mime_type`, `metadata_payload['extension']`, `checksum_sha256`, `created_at`)
- [ ] T008 Verificar o esquema: rodar `uv run alembic check`. Se acusar drift OU se a implementação adotar o índice parcial `(activity_run_id, key) WHERE key='form_attachment'` / tratamento de `Artifact.status` descritos em `data-model.md` §"Migração Alembic", gerar revisão autogerada com nome descritivo em `migrations/versions/` e criar testes de `upgrade` e `downgrade` em `tests/integration/migrations/`. Se nada mudar, registrar em nota que `alembic check` está limpo

**Checkpoint**: base pronta — user stories podem começar

---

## Phase 3: User Story 1 - Proponente anexa um documento e submete a proposta (Priority: P1) 🎯 MVP

**Goal**: o proponente envia um arquivo (POP) para um campo `file_upload` e submete
a proposta com o anexo incluído no dossiê.

**Independent Test**: instanciar processo com campo `file_upload`, autenticar como
proponente, `POST` do arquivo, `GET` do formulário mostrando o anexo, `POST` de
submissão com sucesso; anexo associado ao `proposal_dossier` e com `status='SUBMITTED'`.

### Tests for User Story 1 ⚠️ (escrever primeiro, ver falhar)

- [ ] T009 [P] [US1] `tests/unit/core/test_attachment_service.py`: allowlist por campo vs default `['pdf','docx','doc','png','jpg','jpeg']`; teto por campo (`max_size_mb`) vs `ATTACHMENT_MAX_SIZE_MB=25`; arquivo 0 byte → `empty_file`; excesso → `file_too_large` sem deixar arquivo parcial; `sha256` correto; caminho `f'{process_id}/{artifact_id}.{ext}'`
- [ ] T010 [P] [US1] `tests/api/routers/test_form_attachments.py::test_upload_then_submit_bundles_attachment`: `POST` multipart → 200 com `attachment.checksum_sha256` e `replaced_previous=false`; `GET .../form` traz `fields[].attachment` preenchido e `values` sem a chave do campo `file_upload`; `POST .../form` (submissão) → 200; `Artifact` `key='proposal_dossier'` com `metadata_payload['attachments'][0]['field_key']`; `Artifact` do anexo com `status='SUBMITTED'`
- [ ] T011 [P] [US1] `tests/api/routers/test_form_attachments.py::test_submit_blocked_without_required_attachment`: sem upload prévio, `POST .../form` → 422 com erro de campo `code='attachment_required'`; `FormInstance.is_submitted` permanece `false` (atômico)

### Implementation for User Story 1

- [ ] T012 [US1] Implementar `POST /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment` em `src/pivma/routers/forms.py`: parâmetros `id: UUID`, `activity_key: str`, `field_key: str`, `file: UploadFile`, `session: Session`, `current_user: CurrentUser`, `_: TrustedOrigin`; autorizar/carregar via `get_current_form_instance(session, id, activity_key, current_user.id)` (mapear `NotFoundError`→404); 409 `form_submitted` se `form_instance.is_submitted`; localizar o `FormField` por `field_key` (404 se inexistente) e 422 `not_a_file_field` se `field_type != 'file_upload'`; validar e gravar via `attachment_service`; criar `Artifact(process_instance_id=id, activity_run_id=<run>.id, key='form_attachment', name=<nome original truncado a 255>, file_path=<relpath>, file_size=<size>, mime_type=<file.content_type>, checksum_sha256=<hash>, metadata_payload={'field_key': field_key, 'original_filename': <nome>, 'extension': <ext>}, status='DRAFT')` + `set_creation_audit`; upsert do `FormValue` do campo e `file_attachment_id = artifact.id`; `AuditEvent(process_instance_id=id, activity_run_id=<run>.id, user_id=current_user.id, event_type='FORM_ATTACHMENT_UPLOADED', context_data={'activity_key','field_key'})`; `commit`; retornar `AttachmentUploadResponse`
- [ ] T013 [US1] Em `src/pivma/routers/forms.py` `get_activity_form`: para cada `FormField` com `field_type == 'file_upload'`, resolver o `FormValue` ativo e, se `file_attachment_id` não nulo, carregar o `Artifact` e preencher `FormFieldDefinition.attachment` com `_attachment_metadata(...)`; senão `None`
- [ ] T014 [US1] Em `src/pivma/core/process_engine.py` `submit_proposal_form`: antes de `_validate_form_values`, carregar os `FormValue` ativos da instância; para cada `FormField` com `field_type == 'file_upload'` e `is_required is True` sem `FormValue` ativo com `file_attachment_id`, coletar erro `{'field_key': f.field_key, 'code': 'attachment_required', 'message': ...}` e, havendo erros, `raise ValidationError('Anexos obrigatórios ausentes.', errors=[...])` antes de qualquer mutação
- [ ] T015 [US1] Em `src/pivma/core/process_engine.py` `submit_proposal_form`: após `_save_submitted_values`, para cada campo `file_upload` com anexo ativo, definir `artifact.status = 'SUBMITTED'` + `set_update_audit(user_id)` e montar `attachments = [{'field_key','artifact_id','filename','size','mime_type','checksum'}]`; gravar em `artifact_dossier.metadata_payload['attachments']` (o `Artifact` `key='proposal_dossier'` já criado nessa função)

**Checkpoint**: US1 funcional e testável isoladamente (MVP)

---

## Phase 4: User Story 2 - Proponente gerencia anexos durante o rascunho (Priority: P2)

**Goal**: enviar, substituir e remover anexos livremente enquanto o formulário é
rascunho, salvando os demais campos normalmente; anexos persistem ao reabrir.

**Independent Test**: enviar anexo, salvar rascunho, reabrir (anexo presente),
substituir (`replaced_previous=true`), salvar de novo, remover (campo vazio);
rejeições de extensão/tamanho/vazio preservam o anexo anterior.

### Tests for User Story 2 ⚠️

- [ ] T016 [P] [US2] `tests/api/routers/test_form_attachments.py`: `test_replace_reports_previous_and_keeps_one_active`; `test_delete_clears_form_value`; `test_draft_save_succeeds_with_file_field_present` (`PUT .../form` com `{'values': {'method_title': '...'}}` → 200 mesmo com campo `file_upload` no formulário); `test_draft_rejects_inline_file_upload_value` (`PUT` com a chave do campo `file_upload` → 422, erro de campo `code='file_upload_uses_attachment_endpoint'`); `test_invalid_upload_preserves_previous` (extensão/tamanho/vazio recusados; anexo anterior intacto)
- [ ] T017 [P] [US2] `tests/integration/database/test_form_value_attachment_link.py`: no máximo um `Artifact` de anexo ativo (`deleted_at IS NULL`) por `(form_instance_id, form_field_id)`; substituir marca `deleted_at` no `Artifact` anterior; remover marca `deleted_at` e zera `FormValue.file_attachment_id`
- [ ] T018 [P] [US2] Substituir `tests/api/routers/test_form_submission.py::test_draft_rejects_file_upload_without_persisting_artifact` pelo novo comportamento (rascunho não recusa o formulário só por conter `file_upload`; valor inline vira `file_upload_uses_attachment_endpoint`)

### Implementation for User Story 2

- [ ] T019 [US2] Adicionar caminho de substituição na rota `POST` de T012 (`src/pivma/routers/forms.py`): se o `FormValue` do campo já tem `file_attachment_id`, `set_deletion_audit` no `Artifact` antigo, agendar `attachment_service.remove_file_best_effort(<abs path antigo>)` para depois do `commit`, apontar `file_attachment_id` para o novo e responder `replaced_previous=true`
- [ ] T020 [US2] Implementar `DELETE /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment` em `src/pivma/routers/forms.py` (`current_user: CurrentUser`, `_: TrustedOrigin`): mesmas guardas de proponente/rascunho da T012; 409 `form_submitted` se submetido; 404 se campo inexistente ou sem anexo; `set_deletion_audit` no `Artifact`, `FormValue.file_attachment_id = None`, `remove_file_best_effort` pós-commit, `AuditEvent('FORM_ATTACHMENT_REMOVED')`; retornar `AttachmentRemovedResponse`
- [ ] T021 [US2] Em `src/pivma/core/process_engine.py` `_validate_draft_values`: trocar a branch `file_upload` — hoje sempre gera `file_upload_not_supported`. Novo: só gerar erro quando `field_key` do valor recebido é de campo `file_upload` (o cliente mandou valor inline), com `code='file_upload_uses_attachment_endpoint'` e mensagem apontando a rota de anexo; nenhum erro quando o formulário apenas contém campos `file_upload` sem valor no corpo

**Checkpoint**: US1 e US2 funcionam de forma independente

---

## Phase 5: User Story 3 - Avaliador de triagem consulta os anexos da proposta (Priority: P2)

**Goal**: quem tem escopo de leitura do processo baixa o arquivo original.

**Independent Test**: com proposta submetida e processo em triagem, avaliador
autorizado baixa o anexo e o `sha256` bate com o do upload; usuário sem escopo
recebe 404.

### Tests for User Story 3 ⚠️

- [ ] T022 [P] [US3] `tests/api/routers/test_form_attachments.py`: `test_triage_evaluator_downloads_original` (processo em `TRIAGE`, `GET` → 200, `sha256(body)` == checksum do upload, header `Content-Disposition` com `filename`); `test_download_denied_without_read_scope` (usuário sem vínculo → 404, sem revelar existência); `test_owner_downloads_during_submission` (proponente dono baixa enquanto `SUBMISSION`); `test_download_404_when_field_has_no_attachment`

### Implementation for User Story 3

- [ ] T023 [US3] Implementar `GET /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment` em `src/pivma/routers/forms.py` (`current_user: CurrentUser`): autorizar reutilizando `get_current_form_instance(session, id, activity_key, current_user.id)` (mapear `NotFoundError`→404, sem detalhar); localizar `FormField` `file_upload` e o `Artifact` ativo (404 se ausente); retornar `fastapi.responses.FileResponse(path=<Settings.ATTACHMENTS_DIR>/<artifact.file_path>, media_type=artifact.mime_type or 'application/octet-stream', filename=<nome sanitizado>)` e headers `Content-Disposition: attachment; filename*=UTF-8''<nome>` e `ETag: "<artifact.checksum_sha256>"`

**Checkpoint**: US1, US2 e US3 independentes

---

## Phase 6: User Story 4 - Anexos ficam fora da avaliação por IA (Priority: P3)

**Goal**: campos `file_upload` não entram no pipeline de IA; conteúdo do arquivo
nunca vai ao provedor; campo registrado como "não avaliado"; execução conclui.

**Independent Test**: `EvaluationAssignment` alcançando um campo `file_upload`;
disparar pré-avaliação; provedor não recebe conteúdo do arquivo; snapshot registra
`ai_status: 'not_evaluated'`; `EvaluationRun.status == 'completed'`.

### Tests for User Story 4 ⚠️

- [ ] T024 [P] [US4] `tests/integration/ai/test_pre_evaluation_skips_attachments.py`: assignment que cobre um campo `file_upload` → nenhum `PipelineRequest`/chamada de provedor com o conteúdo do arquivo; `EvaluationRun.evaluated_content_snapshot` contém `{field_key, label, ai_status: 'not_evaluated', reason: 'attachment_not_ai_evaluable'}`; `EvaluationRun.status == 'completed'`
- [ ] T025 [P] [US4] mesmo arquivo: `test_form_with_only_attachment_ai_fields_routes_to_triage` — quando todos os campos alcançados por IA são `file_upload`, `_execute` conclui e o processo segue para triagem (equivalente a "sem avaliações por IA associadas")

### Implementation for User Story 4

- [ ] T026 [US4] Em `src/pivma/core/pre_evaluation_service.py` (`_execute` e/ou `_target_content`): filtrar, por assignment, as `field_keys` cujo `fields_by_key[key].field_type == 'file_upload'`; se a assignment não sobrar nenhuma chave de texto, `continue` (não chamar o provedor); acumular a lista de campos de anexo pulados
- [ ] T027 [US4] Em `src/pivma/core/pre_evaluation_service.py` `_execute`: registrar cada campo pulado em `run.evaluated_content_snapshot` como `{'field_key','label','ai_status': 'not_evaluated','reason': 'attachment_not_ai_evaluable'}`; garantir que o caminho "sem itens" (`items == []`) conclui `status='completed'` e roteia como o ramo atual sem assignment (chama `_unblock_triage_activity` / `_set_process_status(..., 'TRIAGE')`); verificar o retorno de `consolidate([])` e tratar explicitamente se necessário

**Checkpoint**: todas as user stories independentes

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: critério de conclusão (demo + seed + docs) e portões de qualidade

- [ ] T028 [P] Adicionar campo `file_upload` em `src/pivma/templates_data/05_proof_of_concept.yaml` no formulário de submissão: `field_key: pop_document`, `label: "POP do Método"`, `is_required: false`, `section: "Documentação de Suporte"`, `validation_rules: {allowed_extensions: ["pdf", "docx"], max_size_mb: 25}`; coordenar com a estrutura do FP (Spec 015) para não descaracterizar as 9 seções
- [ ] T029 Atualizar `scripts/seeds/seed_forms.py` e/ou `scripts/seeds/seed_all.py` para que `seed_all` provisione um processo cujo formulário de submissão tenha o campo de anexo (e opcionalmente um anexo de exemplo já enviado), mantendo a carga idempotente
- [ ] T030 [P] Criar demo `demos/attachments/` (ou estender `demos/submission/`) exercitando contra a API real: enviar arquivo → submeter → baixar como avaliador; seguir o padrão visual compartilhado (Spec 015); registrar no catálogo `demos/index.html`
- [ ] T031 [P] Atualizar `src/pivma/templates_data/README.md` (Seções 4 e 5.2) declarando que `file_upload` está operacional e resumindo as três rotas de anexo (`POST`/`GET`/`DELETE .../form/fields/{field_key}/attachment`)
- [ ] T032 [P] (Opcional, constituição VI) Adicionar `TrustedOrigin` às rotas existentes `save_form_draft` e `submit_form` em `src/pivma/routers/forms.py`; ajustar os testes afetados em `tests/api/routers/test_form_submission.py` para enviar `Origin: https://testserver`
- [ ] T033 Rodar `uv run poe format`, `uv run poe lint`, `uv run poe test` (todos verdes) e `uv run alembic check` (limpo, ou revisão nova com testes `upgrade`/`downgrade`)
- [ ] T034 Executar os 5 cenários de `specs/016-form-attachments/quickstart.md` contra a API real após `uv run python -m scripts.seeds.seed_all`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3–6)**: dependem da Fase 2
  - US1 é o MVP; US2, US3, US4 podem seguir em paralelo após a Fase 2
- **Polish (Phase 7)**: depende das user stories desejadas concluídas

### User Story Dependencies

- **US1 (P1)**: só depende da Fase 2
- **US2 (P2)**: só depende da Fase 2; T019 estende a rota criada em T012 (mesmo arquivo — coordenar se paralelo com US1)
- **US3 (P2)**: só depende da Fase 2 (para teste ponta a ponta usa um anexo criado pela rota de T012)
- **US4 (P3)**: só depende da Fase 2; independente das rotas HTTP (mexe em `pre_evaluation_service.py`)

### Within Each User Story

- Testes primeiro (ver falhar) → implementação
- `attachment_service` (Fase 2) antes das rotas
- Rotas antes dos ajustes de submissão que dependem de anexos existentes

### Parallel Opportunities

- T002, T003 em paralelo no Setup
- T006, T007 em paralelo (após T005) na Fase 2
- Todos os testes marcados [P] de uma mesma story em paralelo
- US2, US3, US4 por pessoas diferentes após a Fase 2 (US4 é o mais isolado — arquivo distinto)
- Fase 7: T028, T030, T031, T032 em paralelo

---

## Parallel Example: User Story 1

```bash
# Testes da US1 juntos (devem falhar antes da implementação):
Task: "tests/unit/core/test_attachment_service.py"
Task: "tests/api/routers/test_form_attachments.py::test_upload_then_submit_bundles_attachment"
Task: "tests/api/routers/test_form_attachments.py::test_submit_blocked_without_required_attachment"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Fase 1: Setup (T001–T004)
2. Fase 2: Foundational (T005–T008) — CRÍTICO
3. Fase 3: US1 (T009–T015)
4. **PARAR e VALIDAR**: quickstart cenários 1–2
5. Demo/deploy se pronto

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → validar → demo (MVP: anexar + submeter)
3. US2 → validar → demo (gerir no rascunho)
4. US3 → validar → demo (download pelo avaliador)
5. US4 → validar (salvaguarda de IA)
6. Fase 7 → demo + seed + docs + portões

---

## Notes

- `[P]` = arquivos diferentes, sem dependências pendentes
- Skill `fastapi-testing-methodology` obrigatória ao escrever/alterar testes; fixture `engine` (Testcontainers `pgvector/pgvector:pg17`), factories de `tests/factories/`, padrão Arrange–Act–Assert
- Skill `andrej-karpathy-skills:karpathy-guidelines` exigida pela constituição para código/refatoração — **não instalada neste ambiente Claude Code**; declarar a lacuna ao implementar
- `stop-slop` (prosa: README/demo) sem equivalente instalado — declarar a lacuna
- Commit após cada tarefa ou grupo lógico; PR com alvo `main` salvo indicação em contrário
- Critério de conclusão (AGENTS.md / constituição III): demo + seed funcionais contra a API real

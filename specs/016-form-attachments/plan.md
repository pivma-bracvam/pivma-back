# Implementation Plan: Anexos de Arquivo em Formulários

**Branch**: `016-form-attachments` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-form-attachments/spec.md`

## Summary

Tornar operacional o tipo de campo `file_upload` já existente na sintaxe de
formulários. O proponente envia um arquivo (PDF, DOCX, PNG, JPEG e o que o campo
declarar) para um campo de anexo por meio de rotas dedicadas de upload
(multipart), gerencia-o durante o rascunho (substituir/remover) e o submete junto
com a proposta. Avaliadores de triagem e administradores baixam o arquivo
original. Campos de anexo ficam fora do pipeline de pré-avaliação por IA: o
conteúdo nunca é enviado ao provedor; a execução registra o campo como "não
avaliado" e conclui normalmente.

Abordagem técnica: reaproveitar o modelo `Artifact` (já com `file_path`,
`file_size`, `mime_type`, `checksum_sha256`, `metadata_payload`, `status`) e o
vínculo `FormValue.file_attachment_id` (já existente, hoje inutilizado).
Armazenamento em disco local sob diretório configurável via `Settings`. Nenhuma
migração de esquema nova é estritamente necessária para os campos já presentes;
uma migração pode ser gerada apenas se ajustes de constraint/índice forem
decididos na implementação (ver Data Model). Endpoints novos vivem em
`src/pivma/routers/forms.py`; a lógica de domínio em
`src/pivma/core/process_engine.py` (validação de submissão) e um novo módulo
`src/pivma/core/attachment_service.py` para o ciclo de vida do arquivo.

## Technical Context

**Language/Version**: Python `>=3.14`

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2,
`pydantic-settings`, Alembic, PostgreSQL + `pgvector`, `structlog`,
`python-multipart` (já presente em `uv.lock`; confirmar como dependência direta
de projeto)

**Storage**: PostgreSQL para metadados (`artifacts`, `form_values`); sistema de
arquivos local para o binário, sob `Settings.ATTACHMENTS_DIR` (padrão
`var/attachments/` relativo à raiz, criado sob demanda)

**Testing**: pytest + pytest-asyncio + Testcontainers (`pgvector/pgvector:pg17`),
factories em `tests/factories/`, camadas `tests/unit/`, `tests/api/routers/`,
`tests/integration/database/`, `tests/integration/migrations/`

**Target Platform**: Servidor Linux (API FastAPI async)

**Project Type**: Web service (backend único) + demos descartáveis em `demos/`

**Performance Goals**: Padrão de aplicação web; upload de arquivos até o teto de
tamanho (padrão 25 MB) sem carregar o arquivo inteiro em memória mais de uma vez;
download por streaming

**Constraints**: Sem serviço externo de storage/antivírus nesta entrega;
validação por extensão declarada + tamanho; imutabilidade após submissão;
conteúdo de anexo nunca trafega para o provedor de IA

**Scale/Scope**: Dezenas de processos ativos, poucos anexos por formulário
(1 arquivo por campo `file_upload`); volume de arquivos pequeno

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Situação | Nota |
|---|---|---|
| I. Especificação antes da implementação | ✅ | `spec.md` aprovado; este `plan.md` precede o código. |
| II. Domínio puro na API, demos descartáveis | ✅ | Endpoints de anexo são requisito de domínio (proponente anexa POP); nenhuma rota existe só para a demo. A demo consumirá a API real. |
| III. Demonstração como critério de conclusão | ✅ (planejado) | Demo em `demos/` + seed em `scripts/seeds/` entregues junto (SC-009). Provável reutilizar a demo de submissão existente. |
| IV. Qualidade verificável | ✅ (planejado) | Testes nas 4 camadas; `poe format/lint/test` verdes; skill `fastapi-testing-methodology` ao escrever testes. |
| V. Auditabilidade e rastreabilidade | ✅ | `Artifact` e `FormValue` herdam `AuditMixin`; remoção de anexo é lógica (`set_deletion_audit`); `AuditEvent` para upload/replace/remove. |
| VI. Segurança por padrão | ⚠️ → ✅ | Rotas de mutação (`POST`/`DELETE` de anexo) recebem `CurrentUser` **e** `TrustedOrigin` (hoje `forms.py` não usa `TrustedOrigin` — dívida pré-existente; as rotas novas já entram conformes; alinhar as antigas fica como item opcional em `tasks.md`). Download valida `CurrentUser` + escopo de leitura do processo. Erros não vazam caminho de arquivo nem stack. |

**Restrições de stack**: `Settings.ATTACHMENTS_DIR` e `Settings.ATTACHMENT_MAX_SIZE_MB`
entram em `src/pivma/core/settings.py` (proibida leitura ad hoc de env). Se
`models.py` mudar, gerar revisão Alembic com teste upgrade/downgrade.

**Resultado do gate**: PASS (nenhuma violação exige *Complexity Tracking*).

**Re-check pós-Fase 1**: PASS. O design não introduz tabela, endpoint facilitador
nem dependência além de promover `python-multipart` a dependência direta. `Artifact`
e `FormValue` já herdam `AuditMixin`. As rotas de mutação novas entram com
`TrustedOrigin`. Nenhuma nova entrada em *Complexity Tracking*.

## Project Structure

### Documentation (this feature)

```text
specs/016-form-attachments/
├── plan.md              # Este arquivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   └── form-attachments.md   # Contrato HTTP das rotas de anexo
├── checklists/
│   └── requirements.md  # (do /speckit-specify)
└── tasks.md             # (/speckit-tasks — ainda não criado)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── settings.py                 # + ATTACHMENTS_DIR, ATTACHMENT_MAX_SIZE_MB, ATTACHMENT_DEFAULT_EXTENSIONS
│   ├── attachment_service.py       # NOVO: ciclo de vida (save/replace/delete/load), validação, checksum, resolução de caminho
│   ├── process_engine.py           # submissão: exigir anexo em campo file_upload obrigatório; incluir anexos no dossiê; rascunho não recusa mais só por conter file_upload
│   └── pre_evaluation_service.py    # excluir campos file_upload do pipeline; registrar "não avaliado"
├── routers/
│   └── forms.py                    # NOVO: POST/DELETE/GET .../form/fields/{field_key}/attachment
├── schemas.py                      # + AttachmentMetadata, FormFieldDefinition.attachment, resposta de upload
└── core/database/models.py         # possivelmente inalterado (ver data-model.md); Artifact.status + índice opcional

tests/
├── unit/core/
│   ├── test_attachment_service.py      # validação de extensão/tamanho/vazio, checksum, resolução de caminho
│   └── test_pre_evaluation_skips_files.py
├── api/routers/
│   └── test_form_attachments.py        # upload/replace/remove/download, RBAC, imutabilidade pós-submissão, obrigatório na submissão
├── integration/database/
│   └── test_form_value_attachment_link.py   # unicidade de 1 anexo ativo por campo, soft delete
└── integration/migrations/
    └── (se houver revisão nova) test upgrade/downgrade

demos/
└── submission/ (ou nova pasta)     # exercitar upload + submissão + download via API real
scripts/seeds/
└── seed_all + template YAML de um processo com campo file_upload
```

**Structure Decision**: Projeto de backend único já estabelecido. A feature
adiciona um serviço de domínio (`attachment_service.py`) e três rotas no router
de formulários existente, seguindo o padrão dos demais routers. Nenhuma nova
fronteira de módulo.

## Complexity Tracking

*Sem violações constitucionais que exijam justificativa.*

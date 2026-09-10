# Quickstart / Guia de Validação: Anexos de Formulário

Prova de que a feature funciona ponta a ponta contra a API real. Detalhes de
contrato em [contracts/form-attachments.md](./contracts/form-attachments.md);
modelo em [data-model.md](./data-model.md).

## Pré-requisitos

- Banco migrado e vazio; Testcontainers disponível para a suíte.
- `Settings` com `ATTACHMENTS_DIR` apontando para um diretório gravável
  (padrão `var/attachments/`).
- Um template de processo cujo formulário de submissão tenha um campo
  `file_upload` (ver seed abaixo).

## Setup

```bash
uv sync
uv run alembic upgrade head
uv run python -m scripts.seeds.seed_all
```

O seed deve provisionar: usuários (`proponent_user`, `triage_evaluator`, `admin`),
um processo instanciado cujo formulário de submissão contém um campo
`file_upload` (ex.: `pop_document`, obrigatório) e a configuração de IA
determinística.

## Cenário 1 — Proponente anexa um POP e submete (US1, P1)

```bash
# autenticar como proponente (cookie access_token) — ver tests/api/routers/test_rbac_router.authenticate

# 1. enviar o arquivo
curl -sS -X POST \
  -H "Origin: http://localhost" -b cookies.txt \
  -F "file=@./POP-exemplo.pdf" \
  "$API/processes/$PID/activities/proposal_submission/form/fields/pop_document/attachment"
# espera 200 com attachment.checksum_sha256

# 2. conferir que o formulário mostra o anexo e values não traz pop_document
curl -sS -b cookies.txt "$API/processes/$PID/activities/proposal_submission/form"
# espera fields[pop_document].attachment != null ; values sem "pop_document"

# 3. preencher os demais campos e submeter
curl -sS -X POST -H "Origin: http://localhost" -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"values":{"method_title":"Método X"}}' \
  "$API/processes/$PID/activities/proposal_submission/form"
# espera 200; processo sai de SUBMISSION
```

**Resultado esperado**: submissão conclui; dossiê tem
`metadata_payload.attachments[0].field_key == "pop_document"`; `Artifact` do
anexo com `status == "SUBMITTED"`.

## Cenário 2 — Obrigatório ausente bloqueia a submissão (US1 cenário 3)

Sem executar o passo 1 acima, submeter direto → **422**, erro de campo
`code: "attachment_required"`. Nenhum `FormInstance.is_submitted` vira `true`.

## Cenário 3 — Gerenciar no rascunho (US2)

```bash
# substituir
curl ... -F "file=@./POP-v2.pdf" .../fields/pop_document/attachment   # 200, replaced_previous=true
# salvar rascunho dos outros campos continua ok
curl ... -d '{"values":{"method_title":"rascunho"}}' -X PUT .../form  # 200
# reabrir mostra o anexo v2
curl ... .../form   # attachment.filename == "POP-v2.pdf"
# remover
curl ... -X DELETE -H "Origin: http://localhost" .../fields/pop_document/attachment  # 200 removed=true
```

Recusas esperadas: extensão fora da lista → 422 `extension_not_allowed`;
> limite → 413 `file_too_large`; arquivo vazio → 400 `empty_file`. Em todas, o
anexo anterior permanece.

## Cenário 4 — Download pelo avaliador de triagem (US3)

```bash
# com o processo em TRIAGE, autenticado como triage_evaluator
curl -sS -b cookies_triage.txt -o baixado.pdf \
  "$API/processes/$PID/activities/proposal_submission/form/fields/pop_document/attachment"
sha256sum baixado.pdf   # == checksum retornado no upload
```

Usuário sem escopo de leitura do processo → **404** (não revela existência).

## Cenário 5 — Anexo fora da IA (US4)

Configurar uma `EvaluationAssignment` que alcance `pop_document`. Submeter e
disparar a pré-avaliação.

**Resultado esperado**:
- Nenhuma chamada ao provedor de IA com conteúdo do arquivo (verificável com o
  provedor fake / inspeção de `PipelineRequest`).
- `EvaluationRun.evaluated_content_snapshot` contém
  `{field_key: "pop_document", ai_status: "not_evaluated",
  reason: "attachment_not_ai_evaluable"}`.
- `EvaluationRun.status == "completed"`; se não sobrar nenhum campo de texto,
  o processo segue para triagem.

## Portões antes de concluir

```bash
uv run poe format
uv run poe lint
uv run poe test
uv run alembic check   # sem drift, ou revisão nova com teste upgrade/downgrade
```

- Demo em `demos/` exercitando upload + submissão + download contra a API real.
- Seed `seed_all` sozinho habilita a demo (AGENTS.md / constituição III).

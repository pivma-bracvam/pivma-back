# Phase 0 Research: Anexos de Arquivo em Formulários

Nenhum item da Technical Context ficou como `NEEDS CLARIFICATION`. As decisões
abaixo consolidam a análise do código existente e das opções avaliadas.

## D1 — Onde guardar o binário do arquivo

**Decision**: Sistema de arquivos local, sob `Settings.ATTACHMENTS_DIR` (padrão
`var/attachments/`), com layout `\{ATTACHMENTS_DIR\}/\{process_instance_id\}/\{artifact_id\}\{ext\}`.
Metadados (`file_path`, `file_size`, `mime_type`, `checksum_sha256`, nome
original em `metadata_payload`) no registro `Artifact`.

**Rationale**:
- O modelo `Artifact` já tem exatamente esses campos (`file_path` String(500),
  `file_size` BigInteger, `mime_type` String(128), `checksum_sha256` String(64),
  `metadata_payload` JSONB, `status`). Nada novo no esquema.
- O spec exclui serviço externo de storage nesta entrega.
- `artifact_id` como nome de arquivo elimina colisão e path traversal (o nome
  original do usuário nunca vira caminho).
- Diretório por processo facilita limpeza e inspeção manual nas demos.

**Alternatives considered**:
- **Bytea no PostgreSQL**: simplifica backup/atomicidade, mas infla o banco e o
  modelo `Artifact` não tem coluna de conteúdo; exigiria migração e mudaria o
  padrão dos artefatos existentes (dossiê, relatório de IA são só metadados).
- **Objeto em S3/MinIO**: fora de escopo declarado; adiciona dependência e
  configuração.

## D2 — Como o arquivo chega à API

**Decision**: Rotas dedicadas `multipart/form-data`, uma por campo de anexo:
- `POST   /processes/\{id\}/activities/\{activity_key\}/form/fields/\{field_key\}/attachment`
- `DELETE /processes/\{id\}/activities/\{activity_key\}/form/fields/\{field_key\}/attachment`
- `GET    /processes/\{id\}/activities/\{activity_key\}/form/fields/\{field_key\}/attachment`

O corpo JSON de rascunho (`PUT .../form`) e de submissão (`POST .../form`)
**não** transporta arquivos.

**Rationale**:
- `python-multipart` já está resolvido no `uv.lock`; FastAPI `UploadFile`
  transmite em streaming, sem base64 (que incharia payload em ~33%).
- Mantém o contrato JSON dos formulários limpo e tipado; anexos têm ciclo de
  vida próprio (enviar cedo, revisar, trocar) independente do "salvar rascunho".
- Espelha o padrão REST já usado no projeto (rota aninhada ao recurso).

**Alternatives considered**:
- **Base64 dentro de `values` no PUT/POST**: acopla o upload ao salvamento de
  todos os campos, dificulta limites de tamanho por streaming e polui o schema.
- **Endpoint genérico `/artifacts`**: violaria o escopo por campo/atividade e a
  autorização fica difusa; o vínculo com `FormValue` exige o contexto do campo.

## D3 — Interação com salvar rascunho e submeter

**Decision**:
- **Rascunho** (`_validate_draft_values`): parar de recusar *o formulário inteiro*
  quando ele apenas *contém* campos `file_upload`. Recusar apenas se o cliente
  enviar um valor inline para uma chave `file_upload` no JSON, com código
  `file_upload_uses_attachment_endpoint` e mensagem orientando a rota de anexo.
  (Hoje já é assim na prática — o loop itera `values_dict.items()`; só muda a
  mensagem e o código.)
- **Submissão** (`submit_proposal_form`): antes de `_validate_form_values`,
  checar, para cada `FormField` `file_upload` com `is_required=True`, se existe
  `FormValue` ativo com `file_attachment_id` não nulo; caso contrário, erro por
  campo (`attachment_required`).
- **Dossiê**: em `submit_proposal_form`, além de `metadata_payload['values']`,
  gravar `metadata_payload['attachments'] = [\{field_key, artifact_id, filename,
  size, mime_type, checksum\}]` para os campos de anexo com arquivo ativo.

**Rationale**: menor mudança possível; mantém `values_dict` como o contrato dos
campos estruturados e trata anexo como dado à parte, alinhado ao modelo
(`FormValue.file_attachment_id` é uma coluna separada, não `text_value`).

**Alternatives considered**:
- Passar o `field_key → artifact_id` no corpo da submissão: redundante (o vínculo
  já está no banco desde o upload) e abriria brecha para o cliente forjar id.

## D4 — Validação de tipo e tamanho

**Decision**:
- Extensão: derivada do nome do arquivo enviado; precisa estar em
  `field.validation_rules['allowed_extensions']` quando declarado, senão no
  conjunto padrão `Settings.ATTACHMENT_DEFAULT_EXTENSIONS`
  (`pdf, docx, doc, png, jpg, jpeg`).
- Tamanho: `field.validation_rules['max_size_mb']` quando declarado, senão
  `Settings.ATTACHMENT_MAX_SIZE_MB` (padrão 25). Verificado durante o streaming;
  aborta ao ultrapassar, sem gravar arquivo parcial.
- Arquivo vazio (0 byte) ou requisição sem parte de arquivo → recusa
  (`empty_file`).
- `mime_type` gravado é o `content_type` informado pelo cliente (informativo); a
  **inspeção do conteúdo real fica fora de escopo** (registrado como lacuna no
  spec).

**Rationale**: casa com a Seção 5.2 do `templates_data/README.md`
(`allowed_extensions`, `max_size_mb`) e com os exemplos (`max_size_mb: 25`).

**Alternatives considered**:
- Sniffing por *magic bytes* (`python-magic`/`filetype`): adiciona dependência e
  o spec adiou explicitamente a validação por conteúdo.

## D5 — Um arquivo por campo e substituição

**Decision**: O índice único ativo de `form_values` (`form_instance_id`,
`form_field_id`) já garante 1 `FormValue` por campo. O upload:
1. resolve/cria o `FormValue` do campo;
2. se já houver `file_attachment_id`, faz `set_deletion_audit` no `Artifact`
   antigo (soft delete) e agenda remoção do arquivo em disco (best-effort, após
   commit);
3. cria o novo `Artifact`, grava o arquivo, aponta `FormValue.file_attachment_id`
   para ele.

Concorrência: a transação + índice único convergem para um único anexo ativo; o
último commit vence. Arquivos órfãos em disco (raros) são toleráveis e limpáveis.

**Rationale**: sem tabela nova, sem histórico de versões (fora de escopo).

## D6 — Exclusão dos campos de anexo da pré-avaliação por IA

**Decision**: Em `pre_evaluation_service._execute`:
- Ao montar o conteúdo de cada `EvaluationAssignment`, filtrar as `field_keys`
  cujo `FormField.field_type == 'file_upload'` (usando `fields_by_key`, já
  disponível).
- Se, após o filtro, a associação não tiver nenhuma chave de texto, **pular** a
  chamada ao provedor para essa associação (`continue`), sem itens.
- Registrar os campos pulados em `run.evaluated_content_snapshot` (ou no
  `report_payload`) como `\{field_key, label, ai_status: 'not_evaluated',
  reason: 'attachment_not_ai_evaluable'\}`, de forma determinística.
- A execução conclui normalmente (`status='completed'`); se **não sobrar nenhum
  item**, `consolidate([])` deve resultar em conclusão não-negativa que não
  bloqueie o processo — validar o comportamento de `consolidate` para lista
  vazia e, se necessário, tratar o caso "sem itens" como `positive`/segue para
  triagem (equivalente a "sem IA associada", que hoje já segue direto —
  `submit_proposal_form` chama `_unblock_triage_activity` quando não há
  assignment).

**Rationale**: `values` da pré-avaliação vem de `metadata_payload['values']` do
dossiê, que **não** conterá as chaves de anexo (D3), então o conteúdo do arquivo
nunca chega ao provedor mesmo sem mudança. O ajuste em `_execute` garante o
registro explícito de "não avaliado" (FR-019) e o término limpo quando só há
campos de anexo (FR-020). "Mockar internamente" = este registro determinístico,
sem novo endpoint nem provedor.

**Alternatives considered**:
- Não tocar em `pre_evaluation_service` e confiar só no D3: cumpre FR-018 mas não
  FR-019 (registro explícito) nem garante FR-020 (término limpo sem itens).
- Marcar o `EvaluationAssignment` como desabilitado no bootstrap: quebra a
  configuração declarativa e não é dinâmico para campos futuros.

## D7 — Autorização de acesso (download)

**Decision**:
- **Upload/replace/delete**: apenas o proponente efetivo ativo do processo
  (mesma checagem `is_active_effective_proponent` já usada em
  `get_current_form_instance` para status sob o proponente) e enquanto o
  formulário está em rascunho.
- **Download (GET)**: reutiliza `get_current_form_instance(session, id,
  activity_key, current_user.id)`. Se essa função já devolve o formulário para o
  usuário (proponente dono enquanto sob o proponente; qualquer leitor autorizado
  do processo depois — inclui avaliador de triagem e admin conforme o gating de
  status atual), o download é liberado; caso contrário, `404` (sem revelar
  existência). Não se cria novo modelo de permissão.

**Rationale**: o gating de visibilidade por status do processo já implementado em
`get_current_form_instance` é exatamente o "escopo de leitura do processo" pedido
pelo spec (FR-015/FR-016). Reaproveitar evita divergência de regra.

**Alternatives considered**:
- Nova permissão RBAC `attachment.read`: acrescenta superfície de configuração
  sem necessidade; o escopo do processo já é a fronteira correta.

## D8 — Segurança das rotas

**Decision**: `POST` e `DELETE` de anexo recebem `CurrentUser` + `TrustedOrigin`
(constituição VI). `GET` recebe `CurrentUser`. Mensagens de erro genéricas
(`400/403/404/409/413/422`), sem caminho de disco nem stack. Nome de arquivo no
`Content-Disposition` do download sanitizado (RFC 5987 / `filename*`).

`forms.py` hoje não usa `TrustedOrigin` nas rotas de mutação existentes (dívida
pré-existente). Alinhar `PUT`/`POST` antigos entra como tarefa **opcional** em
`tasks.md`, fora do caminho crítico.

## D9 — Dependência `python-multipart`

**Decision**: Promover `python-multipart` a dependência direta no `pyproject.toml`
(hoje presente só como transitiva no `uv.lock`), para o uso de `UploadFile` ser
explícito. Sem outras dependências novas (`hashlib` para checksum,
`pathlib`/`os` para disco, tudo stdlib).

## D10 — Streaming de download

**Decision**: `fastapi.responses.FileResponse` (ou `StreamingResponse` com
leitura em blocos) apontando para `Artifact.file_path`, com `media_type` =
`mime_type` gravado e `Content-Disposition: attachment; filename*=...`. Sem
carregar o arquivo em memória.

## Riscos e lacunas (herdados do spec)

- Sem verificação antivírus nem validação por conteúdo real (só extensão +
  tamanho).
- Arquivos órfãos em disco possíveis em corridas raras de substituição
  concorrente; impacto baixo, limpeza manual.
- `consolidate([])` (lista de itens vazia) precisa ser verificado na
  implementação para o caso "formulário só com campos de anexo".

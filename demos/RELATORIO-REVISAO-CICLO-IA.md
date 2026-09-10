# Revisão do ciclo básico de demos + avaliação por IA (Spec 013)

Data: 2026-09-10. Escopo pedido: revisar os módulos 2, 3, 4, 7 e 8; manter 4
módulos; melhorar o editor de formulário para que "Configurar Avaliação por IA"
leve a um fluxo real por campo; não criar endpoint novo; padronizar as contas de
seed. Este relatório registra o que mudou, o que foi verificado contra a API
rodando em `:8000` e o que continua em aberto.

## 1. Decisões

- **De 6 para 4 módulos no hub.** Ciclo básico: `demos/forms/` (editor + config
  de IA), `demos/submission/` (submissão + pré-avaliação), `demos/triage/`
  (triagem + feedback), `demos/ai-pipeline/` (observabilidade). `demos/users/` e
  `demos/operational-index/` passam a "Ferramentas de apoio" (links no rodapé do
  hub, nada removido).
- **Módulos 7 e 8 (`ai-evaluation-library/`, `ai-evaluation-form-editor/`)
  removidos.** Eram páginas que despejavam respostas de endpoint. A configuração
  por IA foi reconstruída como fluxo real, ancorado no editor de formulário.
- **Contas voltaram ao padrão do `seed_users`** (`admin` / `proponent_user` /
  `triage_evaluator`). O seed próprio com contas customizadas e o uso de
  `/auth/token` foram descartados; tudo usa `POST /auth/login` com
  `{identifier, password}`.

## 2. O que foi feito

### 2.1 Editor de formulário — `demos/forms/index.html`
- Cada campo mostra o checkbox `ai_evaluation_enabled`, um selo com as avaliações
  já associadas (`GET /form-templates/{k}/evaluable-fields`) e o botão
  **Configurar Avaliação por IA →**.
- O botão abre `demos/forms/ai-config.html?template=<k>&field=<f>`.

### 2.2 Página dedicada por campo — `demos/forms/ai-config.html` (nova)
Fluxo completo, só com endpoints já existentes:

| Passo | Endpoint |
| --- | --- |
| Reaproveitar da biblioteca | `GET /ai-evaluations` |
| Criar rascunho | `POST /ai-evaluations` |
| Sugerir critérios | `POST /ai-evaluations/suggest-criteria` |
| Editar critérios | `PATCH /ai-evaluations/{id:uuid}/versions/{n:int}` |
| Testar | `POST /ai-evaluations/{id:uuid}/versions/{n:int}/test` |
| Publicar | `POST /ai-evaluations/{id:uuid}/versions/{n:int}/publish` |
| Associar ao campo | `GET` + `PUT /form-templates/{k}/evaluation-assignments` |

O `PUT` de associações **substitui a lista inteira**; a página faz `GET` das
associações atuais, acrescenta a nova (campo → definição) e reenvia o conjunto,
para não apagar o que já existe.

### 2.3 Submissão — `demos/submission/index.html`
- `submitProposalForm()` passou a ramificar na resposta de
  `POST /processes/{id}/activities/{k}/form`:
  - `pre_evaluation` presente → fluxo Spec 013: cartão "pré-avaliação em
    andamento", botão **Atualizar resultado** (`GET /processes/{id}/pre-evaluation`).
  - `ai_evaluation` presente → fluxo legado (Spec 010), quando o formulário não
    tem associações.
  - nenhum → apenas TRIAGE.
- `refreshPreEvaluation()` mostra o resultado consolidado, os pontos de atenção
  (com severidade), e, em caso negativo/falha, os botões **Corrigir e reenviar**
  e **Ignorar a IA e solicitar intervenção direta do BraCVAM**
  (`POST /processes/{id}/submission/direct-review`).

### 2.3.1 Estado da submissão durante a espera pela IA (ajuste fino — implementado)

**Antes:** a submissão já era travada enquanto a IA processava
(`FormInstance.is_submitted = True`; `save_form_values_draft` e
`submit_proposal_form` recusam alteração com `ConflictError`), mas o
`process.status` **permanecia `SUBMISSION`** — indistinguível de um rascunho.

**Agora (backend):** introduzido o status **`AI_PRE_EVALUATION`**.
`process.status` é `String(32)`, não enum PG — **sem migração**.

- `submit_proposal_form`: quando o template tem avaliações associadas, o processo
  passa a `AI_PRE_EVALUATION` (antes ficava em `SUBMISSION`).
- `pre_evaluation_service._execute`: positivo → `TRIAGE`; negativo/falha →
  `_return_to_proponent` volta a `SUBMISSION` (reabre a submissão). Inalterado.
- `retry_run` (admin): volta o processo a `AI_PRE_EVALUATION` durante o
  reprocessamento.
- Constante `PROPONENT_SCOPED_STATUSES = ('SUBMISSION', 'AI_PRE_EVALUATION')` —
  `get_current_form_instance` e os três filtros de `routers/processes.py`
  (`list`, `get`, `timeline`) tratam os dois estados igual: formulário travado e
  processo visível só ao proponente. `GET /processes/{id}/pre-evaluation` não é
  afetado (guard próprio: proponente / gestor / `ai_evaluations.read`).
- É simétrico ao lado BraCVAM: a atividade de triagem continua com
  `blocked_reason = "Aguardando pré-avaliação automática por IA."`.

Testes: `test_pre_evaluation_submit` ajustado; novos
`test_status_is_ai_pre_evaluation_and_form_locked_while_pending` e
`test_outsider_cannot_see_process_during_ai_pre_evaluation` em
`test_pre_evaluation_get.py`.

**Bug no demo (corrigido):** `demos/submission/` mostrava um cartão fixo —
*"✓ Proposta Submetida com Sucesso! O processo avançou para o status TRIAGE…"* —
sempre que `is_submitted` era `true`, **sem consultar** o estado real. Refresh
durante o processamento mostrava "TRIAGE" com o processo ainda em espera.

Correção (frontend): `renderTransition()` virou a fonte única do cartão —
consulta `GET /processes/{id}` + `GET /processes/{id}/pre-evaluation`:

| Estado real | O que o demo mostra |
| --- | --- |
| `AI_PRE_EVALUATION` / pré-avaliação `in_progress` | "⏳ Aguardando pré-avaliação por IA — travada para edição", selo `AGUARDANDO IA`, auto-refresh 4 s, campos desabilitados |
| `completed` + positiva | "Pré-avaliação positiva — processo em TRIAGE" + link |
| `completed` negativa + `direct_review_request` | "Encaminhada ao BraCVAM (intervenção direta)" + link |
| `completed` negativa/`failed` sem contestação | "Submissão reaberta para correção" — backend abriu nova execução com `is_submitted=false` |
| sem pré-avaliação (fluxo legado) | "Proposta submetida — processo em <status>" |

Selo `.status-AI_PRE_EVALUATION` adicionado em `demos/submission/` e
`demos/triage/`; o painel de triagem também trata `in_progress`.

### 2.4 Triagem — `demos/triage/index.html`
- Novo painel `#triage-pre-evaluation-box`, carregado em `loadPreEvaluation()`
  (`GET /processes/{id}/pre-evaluation`): avaliação/versão usada, execução,
  resultado, provedor, nota de intervenção direta, e por ponto de atenção o
  enunciado, conclusão/severidade, evidência, justificativa e referências.
- Por critério, três opções (`concordo` / `discordo` / `inconclusivo`) + motivo,
  enviadas por `submitPreEvalFeedback()` para
  `POST /processes/{id}/pre-evaluation/{run_id}/feedback`.
- Texto fixo reforça que a decisão de triagem continua humana.

### 2.5 Seed — `scripts/seeds/seed_ai_evaluations.py` (novo, no `seed_all`)
- Publica a avaliação "Verificação de estrutura de POP" (5 critérios, 2
  `critical`) e a associa ao campo `scope_extension_justification` do formulário
  `submission_scope_extension_v1`.
- Cria o processo `[DEMO IA] Extensão de Escopo com Pré-avaliação`, submete com um
  texto propositalmente incompleto → pré-avaliação **negativa** (provedor `fake`
  no seed) → o proponente contesta e solicita intervenção direta → processo em
  **TRIAGE** com relatório da IA pronto para a demo de Triagem.
- Designa `triage_evaluator` como `group_manager` desse processo (ver seção 3).

## 3. Restrição encontrada e contorno

`GET /processes/{id}/pre-evaluation` e
`POST /processes/{id}/pre-evaluation/{run_id}/feedback` são liberados apenas para:
proponente do processo, **gestor do processo (`group_manager`)** ou perfil
**Administrador** (permissão `ai_evaluations.read`, concedida só ao Administrador
pela migração da Spec 013).

O perfil **Revisor** (`triage_evaluator`) **não** tem acesso. Sem contorno, a
demo de Triagem não conseguiria abrir o painel da IA nem registrar feedback com a
conta de avaliador.

**Contorno adotado (sem endpoint novo):** o seed designa `triage_evaluator` como
`group_manager` do processo `[DEMO IA]` — o mesmo mecanismo do endpoint existente
`POST /processes/{id}/participants`. Verificado: com essa designação, a conta lê a
pré-avaliação e registra feedback (`HTTP 200`).

**Decisão pendente do usuário** — qual é a intenção de produto:
1. O triador técnico (Revisor) **deve** ver a evidência da IA? Então falta
   conceder `ai_evaluations.read` (ou uma permissão de leitura equivalente) ao
   perfil Revisor — mudança de RBAC / migração, não de endpoint.
2. A revisão da pré-avaliação é **exclusiva** do gestor BraCVAM / Administrador?
   Então o contorno do seed é só para a demo, e o texto da UI deve deixar claro
   que essa etapa é do gestor.

## 4. Verificações executadas contra `:8000`

- `seed_all` completo sem erro (após corrigir a pendência da seção 5).
- Login `admin` / `proponent_user` / `triage_evaluator` via `/auth/login`: OK.
- `GET /ai-evaluations`, `GET /form-templates/submission_scope_extension_v1/evaluable-fields`,
  `GET .../evaluation-assignments`: formas de resposta batem com o JS das demos.
- `POST /ai-evaluations/suggest-criteria`: retorna critérios (provedor real da
  OpenAI está ativo no servidor).
- Proponente: `POST /processes` (scope_extension) → `POST .../form` →
  `pre_evaluation` assíncrona resolvendo de `in_progress` para `completed`.
- `triage_evaluator` (agora `group_manager`): `GET .../pre-evaluation` e
  `POST .../feedback` → `HTTP 200`.
- Processo `[DEMO IA]` após o seed: `TRIAGE`, pré-avaliação `negative`, 3 pontos
  de atenção (2 `critical`), `direct_review_request` presente.

## 5. Pendência de dados corrigida (não relacionada à Spec 013)

O template `submission_pre_validated_v1` tinha um campo órfão obrigatório
`chave_do_campo` / rótulo "TITULO DO CAMPO" (resíduo de teste manual anterior no
editor de formulário). Ele quebrava `seed_triage` (a proposta fixa não preenchia
esse campo). Removido via `PUT /processes/templates/pre_validated_method/forms/submission_pre_validated_v1`
(endpoint que o próprio editor usa). O YAML canônico
(`src/pivma/templates_data/01_pre_validated_method.yaml`) não contém esse campo.

## 5.1 Associações órfãs bloqueiam o `PUT` (backend)

Remover ou renomear um campo no editor de formulário **não** limpa as
`EvaluationAssignment` que apontavam para ele. A associação órfã fica no banco e,
como `PUT /form-templates/{k}/evaluation-assignments` valida a lista **inteira**
(`_validate_assignment` → `"field_keys inválidos para o template."`), qualquer
nova associação nesse template passa a falhar — a operação é tudo-ou-nada.

Aconteceu em `submission_pre_validated_v1`: duas associações para o campo
`campo_1` (já inexistente). Limpas com `PUT {"assignments": []}`.

Contorno no demo (`demos/forms/ai-config.html`): a página agora recebe `process`
na URL, lê os campos reais do template e, ao associar, **descarta as associações
órfãs** antes de reenviar o `PUT` (avisa quantas removeu). Também bloqueia o
botão quando o campo da URL não existe no template salvo.

**Implementado (Q2, opção B):** `update_form_template_definition` agora expira em
cascata as associações de campos removidos — retira a `field_key` de cada
associação e, se sobrar vazia, desativa a associação. Teste
`test_removing_field_prunes_its_assignments`. A demo mantém o descarte defensivo
para associações já órfãs no banco.

## 6. Decisões do usuário em 2026-09-10 e estado

| # | Decisão | Estado |
| --- | --- | --- |
| Q1 | "BraCVAM" ≠ "Grupo Gestor" — entidades distintas | **Spec 014** (modelo RBAC + migração) |
| Q2 | Limpeza em cascata de associações órfãs — corrigir na origem | **Feito** (seção 5.1) |
| Q3 | Triagem = IA + BraCVAM + Administração (devs); não Grupo Gestor | **Spec 014** (autorização de triagem) |
| Q4 | Incluir o conteúdo avaliado no payload da triagem | **Feito** — `evaluated_content` em `GET .../pre-evaluation` + painel da demo; snapshot dedicado por execução → Spec 014 |
| Q5 | Remover o que foi desenvolvido na Spec 010 | **Spec 014** (remoção do pipeline legado) |
| M1 | Testes dos endpoints de referências normativas | **Feito** (`test_evaluation_references.py`) |
| M3 | Cadeia `falha da IA → intervenção direta → TRIAGE` | **Feito** (`test_direct_review.py`) |
| M4 | Observabilidade do novo fluxo de log | **Spec 014** (junto da remoção da Spec 010) |
| M5, A1, A2, L3, L4 | Ajustes de redação da spec 013 | **Feito** |
| M6 / T067–T073 | Demos validadas em navegador | **Feito** (marcado cumprido) |

### Escopo da Spec 014 (a planejar via `/speckit-specify`)

1. **Semântica BraCVAM.** Novo perfil de acesso para o BraCVAM (distinto de
   "Grupo Gestor"), com permissão de triagem. Migração.
2. **Autorização da triagem.** `save_field_reviews` e `execute_triage_decision`
   hoje **não têm RBAC** (só barram conflito de interesse); passam a exigir a
   permissão BraCVAM. `_ensure_can_read` / `record_feedback` da pré-avaliação
   trocam `is_effective_group_manager` pela permissão BraCVAM. Seed:
   `triage_evaluator` recebe o perfil BraCVAM e o contorno `group_manager` sai.
3. **Remoção da Spec 010.** `ai/pipeline.py`, `ai/steps/*`, `FormAIPipelineEngine`,
   `_run_legacy_field_ai_mock`, `POST /forms/instances/{id}/evaluate-ai`, testes
   e o ramo `ai_evaluation` de `submit_form`. Formulário sem associações passa a
   ir direto à triagem com relatório vazio (FR-027), sem esteira mock.
4. **Snapshot do conteúdo avaliado** por execução de pré-avaliação (coluna
   dedicada), para fidelidade total mesmo após mudança de associação.
5. **M4** — teste de regressão da observabilidade do fluxo novo.

## 7. Ainda em aberto (fora da Spec 014)

- O provedor de IA ativo no servidor é o real (OpenAI); os testes/`test` das
  demos gastam tokens. O seed usa `AI_PROVIDER=fake` só na sua própria execução.

---
Nota de processo: a skill `stop-slop` (revisão de prosa exigida pelo AGENTS.md)
não está instalada para o Claude Code neste ambiente; este relatório não passou
por ela.

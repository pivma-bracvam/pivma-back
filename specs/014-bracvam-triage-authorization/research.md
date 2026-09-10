# Research — Spec 014

Feature já é uma correção sobre código existente; não há tecnologia nova a
pesquisar. As decisões abaixo resolvem as ambiguidades de implementação.

## D1 — Uma permissão nova `triage.review` (não reutilizar `ai_evaluations.read`)

**Decisão**: criar a permissão `triage.review` e usá-la nas quatro ações de
triagem (parecer de campo, decisão, consulta da pré-avaliação, feedback por
critério).

**Rationale**: `ai_evaluations.read` tem semântica de "consultar a **configuração**
de avaliações e seus resultados de teste" e hoje gateia rotas de biblioteca,
versões, referências e `agreement-metrics`. Sobrecarregá-la com "fazer triagem"
mistura dois domínios: quem configura avaliações (equipe que traduz regra
regulatória) não é necessariamente quem decide a triagem, e vice-versa. Uma
permissão dedicada mantém a matriz de acesso legível e permite, no futuro,
atribuir uma sem a outra.

**Alternativas**: (a) reutilizar `ai_evaluations.read` — rejeitada pelo
acoplamento acima; (b) permissão por ação (`triage.review`, `triage.decide`) —
rejeitada por excesso de granularidade para o estágio atual; a spec trata a
triagem como um bloco (US1).

## D2 — `bracvam` recebe também `ai_evaluations.read` e `ai_evaluations.manage`

**Decisão**: a migração concede ao perfil `bracvam` **três** permissões:
`triage.review` (nova), `ai_evaluations.read` e `ai_evaluations.manage` (ambas já
existentes, hoje só do Administrador).

**Rationale**: a Spec 013 (US1, FR-011) diz que quem configura avaliações por IA é
"Administrador **ou Gestor do BraCVAM**". Com o perfil `bracvam` existindo, ele é
o titular natural dessa capacidade — sem isso, um membro do BraCVAM poderia fazer
a triagem mas não montar as avaliações que alimentam a triagem, o que contradiz o
domínio. É uma composição de permissões na mesma migração, não código novo.

**Impacto na spec**: a Assumption "esta feature apenas adiciona um perfil, uma
permissão e vínculos" passa a "um perfil, uma permissão nova e as composições
necessárias (incluindo reaproveitar `ai_evaluations.*` para o novo perfil)".
Atualizar `spec.md` na fase de polish. FR-002..FR-006 (triagem) permanecem como
estão; acrescentar FR-002a cobrindo a configuração de avaliações pelo `bracvam`.

**Alternativas**: conceder só `triage.review` — rejeitada; deixaria o BraCVAM sem
poder configurar avaliações, exigindo Administrador para toda mudança regulatória.

## D3 — Enforcement na borda (router), com a guarda de conflito no serviço

**Decisão**: aplicar `Depends(require_permission(TRIAGE_REVIEW))` nas rotas
`POST /processes/{id}/triage/reviews` e `/triage/decision`
(`src/pivma/routers/triage.py`). Em `pre_evaluation.py`, `_ensure_can_read` e o
check inline de `record_feedback` trocam `is_effective_group_manager(...) or
has_permission(AI_EVALUATIONS_READ)` por `has_permission(TRIAGE_REVIEW)`,
preservando o ramo do proponente (só leitura) e a guarda
`_guard_against_current_conflict` / `has_current_conflict` no serviço.

**Rationale**: consistente com o resto do projeto — `require_permission` é o
padrão para RBAC de rota (ex.: `ai_evaluations.py`, `rbac.py`); a guarda de
conflito é regra de negócio e fica no `process_engine`/`pre_evaluation_service`,
onde já está. `save_field_reviews` e `execute_triage_decision` continuam chamando
`_guard_against_current_conflict` internamente — dupla proteção sem custo.

**Alternativas**: checar permissão dentro do serviço via `AuthorizationError` —
rejeitada; os serviços não recebem o objeto de request e o padrão de RBAC do
projeto é na dependência da rota.

## D4 — Snapshot como coluna JSONB em `evaluation_runs`

**Decisão**: `EvaluationRun.evaluated_content_snapshot: Mapped[list[dict] | None]`
mapeada para `JSONB` (nullable). Formato: `[{"field_key", "label", "value"}]` —
o mesmo já devolvido hoje por `_evaluated_content` / o schema
`EvaluatedContentField`.

**Rationale**: 1:1 com a execução, escrito uma única vez no `_execute`, nunca
atualizado — encaixa em coluna, não justifica tabela. O projeto já usa JSONB em
`evaluation_versions.references`, `evaluation_runs.models_used`,
`artifacts.metadata_payload`. Migração trivial (`op.add_column` /
`op.drop_column`), downgrade não toca linhas.

**Alternativas**: tabela `evaluation_run_content_items` — rejeitada; nenhuma
consulta relacional sobre o conteúdo é prevista, e a spec pede apresentação, não
filtro.

## D5 — Captura só em execução bem-sucedida

**Decisão**: `_execute` grava `run.evaluated_content_snapshot` logo antes de
`run.status = 'completed'`, reaproveitando `fields_by_key`/`values` já carregados.
`_mark_failed` **não** grava snapshot.

**Rationale**: FR-020 fala de "o momento em que uma execução **processa** o
conteúdo". Uma execução que falhou (timeout/erro do provedor) pode nem ter
montado o conteúdo de todos os alvos. Execuções `failed` caem no fallback de
reconstrução (FR-024), que é suficiente para o proponente decidir corrigir ou
contestar.

**Alternativas**: gravar também em `_mark_failed` — adiada; sem valor de
auditoria claro para um resultado que não produziu conclusões.

## D6 — `contracts.py`: remoção cirúrgica, não do arquivo

**Decisão**: remover de `src/pivma/ai/contracts.py` apenas `AIEvaluationVerdict`,
`PipelineContext` e `StepResult` (usados só pela engine legada). Manter
`AIStepExecutionLog`, `OperationalEventIndex` e `PipelineExecutionGroup` — são
compartilhados com o pipeline da Spec 013 (`ai/evaluation_pipeline.py`) e o
`log_service`. Retirar de `PipelineExecutionGroup` o campo `verdict` e o default
`pipeline_name = 'form_ai_field_evaluation'`; `log_service._build_pipeline_group`
deixa de extrair `verdict` do step `verdict_synthesis`.

**Rationale**: apagar o arquivo quebraria a observabilidade nova. A engine legada
(`ai/pipeline.py`, `ai/steps/`) é que sai inteira.

**Alternativas**: manter `verdict` como sempre-`None` — rejeitada; deixa campo
morto no contrato público.

## D7 — `demos/ai-pipeline/` passa a observar, não disparar

**Decisão**: remover de `demos/ai-pipeline/app.js` o bloco que chama
`POST /forms/instances/{id}/evaluate-ai` (o "disparar pipeline interativo"). O
painel mantém o consumo do stream SSE de logs e o agrupamento por
`correlation_id`; o texto passa a orientar o usuário a **disparar uma
pré-avaliação pela demo de submissão** (`demos/submission/`) e acompanhar aqui.

**Rationale**: sem endpoint de disparo manual (FR-014), o único gerador de
execuções é a submissão real — que é o cenário verdadeiro (Princípio II/III). O
agrupamento por `correlation_id` já funciona para o fluxo novo.

**Alternativas**: manter um botão que cria processo + submete formulário pela
própria página — rejeitada; duplicaria a demo de submissão e violaria "uma demo
por caso de uso".

## D8 — Migração de RBAC: IDs fixos e limpeza no downgrade

**Decisão**: seguir o padrão de `8b701d7bfeae` — UUIDs fixos para o perfil
(`system_key='bracvam'`), a permissão e cada composição. O `downgrade` remove, na
ordem: `user_access_profiles` do perfil bracvam → `access_profile_permissions`
das composições criadas → `permissions` (`triage.review`) → `access_profiles`
(`bracvam`). Não remove `ai_evaluations.*` (permissões pré-existentes), só as
composições `bracvam↔ai_evaluations.*` que esta migração criou.

**Rationale**: reversibilidade completa exigida pelo Princípio V e pela restrição
de migrações; o teste de downgrade (FR-009, SC-008) verifica ausência de órfãos.

**Bloco de dados**: `access_profiles` tem `system_key` único; usar
`system_key='bracvam'`, `name='BraCVAM'`, `description` curta. UUID do perfil:
próximo livre na faixa `00000000-0000-0000-0000-00000000000a` (perfis 1..9 já
usados 0001..0009). Permissão `triage.review`: faixa `...010c` (010a/010b são
`ai_evaluations.*`).

## D9 — Processos legados e o ramo "sem associações"

**Decisão**: o ramo `else` de `submit_proposal_form` (formulário sem
`EvaluationAssignment`) passa a apenas: `_unblock_triage_activity` + `process.
status = 'TRIAGE'` + `set_update_audit` + `AuditEvent('SUBMISSION_SUBMITTED')`.
Sem artefato de parecer, sem `pending_run`. Retorno da função continua a 4-tupla
`(act, run, artifact, None)`.

**Rationale**: é literalmente o que a Spec 013 FR-027 já promete; o mock só
existia como resquício da Spec 010. Processos antigos que já têm
`artifact.metadata_payload['ai_evaluation']` mantêm o artefato (histórico); a rota
de leitura de formulário deixa de expor o campo, mas o dado persiste no JSONB.

## Achados do /speckit-analyze da Spec 013 fechados por esta feature

- **L1** (dois pipelines coexistindo) → US2.
- **M4** (observabilidade do fluxo novo sem teste) → US4.
- **M2/FR-039** parcialmente tratado na Spec 013; o snapshot (US3) completa.

# Pesquisa: Exclusão (Soft-Delete) e Arquivamento de Processos

## Critério de exclusão

**Decision**: Qualquer processo em estado não-terminal (diferente de `CLOSED`, `CANCELLED`, `ARCHIVED`) pode ser excluído, independentemente de já ter sido formalmente submetido.

**Rationale**: A distinção anterior (rascunho nunca submetido vs. processo em pipeline) só existia para justificar dois tratamentos diferentes — remoção física versus preservação de histórico. Com a exclusão passando a ser sempre lógica (soft-delete) e sempre preservando histórico e documentos, essa distinção deixa de ter efeito prático na autorização ou no resultado da operação.

**Alternatives considered**: Manter a checagem `_has_formal_submission` faria a exclusão continuar recusando processos já submetidos, reproduzindo a fragmentação que a revisão de 2026-09-13 pediu para eliminar.

## Soft-delete e reaproveitamento da cascata existente

**Decision**: A exclusão reaproveita `_cancel_process_locked` (cascata de cancelamento de fases, atividades, execuções, tarefas e avaliações automáticas ainda não terminais), removendo apenas sua guarda `if not _has_formal_submission: raise ConflictError`. Além de `process.status = CANCELLED` e `closed_at`, a exclusão agora também chama `process.set_deletion_audit(user_id)` (preenchendo `deleted_at`/`deleted_by` via `AuditMixin`).

**Rationale**: `CANCELLED` não é um status órfão: ele já é o resultado terminal usado por subordinados (`Phase`, `ActivityInstance`, `ActivityRun`, `Task`, `EvaluationRun`) independentemente de quem cancela o processo pai. Reaproveitar essa função existente mantém `ARCHIVE` e `TERMINAL_PROCESS_STATUSES` inalterados e torna a exclusão naturalmente não-idempotente sobre processos já terminais, sem regra nova baseada em `deleted_at`.

**Alternatives considered**: Introduzir um status novo (`DELETED`) foi descartado pela spec desde a versão original. Deixar o `status` congelado no valor anterior (sem transicionar para `CANCELLED`) foi descartado porque duplicaria o significado de "processo encerrado" em dois campos (`status` e `deleted_at`) sem necessidade, e quebraria a pré-condição existente de `ARCHIVE` (`status in {CLOSED, CANCELLED}`).

## Preservação de documentos em disco

**Decision**: A exclusão nunca mais chama `remove_process_attachments`; os binários em `ATTACHMENTS_DIR/{process_id}/` permanecem no disco em qualquer exclusão, independentemente de o processo ter sido submetido ou não.

**Rationale**: Decisão explícita do usuário (Clarification 2026-09-13, Q3): rastreabilidade regulatória uniforme prevalece sobre a economia de armazenamento que motivava a remoção física de rascunhos-lixo na versão anterior desta feature.

**Alternatives considered**: Preservar documentos apenas para processos já submetidos e continuar removendo fisicamente os de rascunhos nunca submetidos foi rejeitado por reintroduzir uma ramificação por histórico de submissão dentro do mesmo endpoint — exatamente a fragmentação que esta revisão elimina.

## Filtro de leitura global (soft-delete)

**Decision**: Registrar um listener `do_orm_execute` na `Session` síncrona subjacente (via `sqlalchemy.event.listens_for(Session, 'do_orm_execute')`) em `core/database/__init__.py`, aplicando `with_loader_criteria(AuditMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)` a toda consulta `SELECT` cujo `execution_options` não contenha `skip_soft_delete_filter=True`.

**Rationale**: `AuditMixin` não é uma classe mapeada por si só (é um mixin de dataclass; cada modelo concreto é decorado individualmente com `@table_registry.mapped_as_dataclass`), mas `with_loader_criteria` suporta exatamente esse padrão — aplicar o critério a qualquer classe mapeada que seja subclasse do mixin informado, mesmo que o mixin em si não seja mapeado. O evento dispara mesmo sob `AsyncSession`, pois ela delega a uma `Session` síncrona internamente (padrão documentado do SQLAlchemy 2.0 para `AsyncSession`). Isso cobre toda entidade soft-deletável do sistema, não apenas processos, atendendo à decisão explícita do usuário (Clarification 2026-09-13, Q5) de tratar isso como rede de segurança global.

**Fraquezas conhecidas, aceitas conscientemente**:
- O listener só intercepta `execution_state.is_select`; um `update(Model)...`/`delete(Model)...` em massa (bulk, sem carregar instâncias) não passa pelo filtro. Nenhum código atual faz isso sobre entidades `AuditMixin`, mas é uma lacuna a documentar para revisões futuras.
- Os filtros manuais `deleted_at.is_(None)` já existentes em `authorization.py` e outros módulos continuam necessários onde já estão — o listener é uma camada adicional, não uma substituição, e não deve ser usado como justificativa para removê-los.
- Qualquer consulta que precise enxergar registros soft-deletados (ex.: a futura consulta administrativa mencionada como INFERÊNCIA na spec) precisa passar `execution_options(skip_soft_delete_filter=True)` explicitamente; não há como o SQLAlchemy alertar em tempo de escrita sobre um lugar que esqueceu de fazer isso.

**Alternatives considered**: Restringir o listener a `ProcessInstance` apenas (recomendação original desta revisão) reduziria o raio de impacto, mas foi conscientemente rejeitado pelo usuário, que preferiu a rede de segurança valer para todo o sistema desde já.

## Comando HTTP e apoio ao front-end

**Decision**: Expor apenas `DELETE /processes/{id}` (soft-delete, `204 No Content`) e `PATCH /processes/{id}/archive` (`200 OK` com `status`/`available_actions`), ambos sem corpo de justificativa. Os endpoints `PATCH /processes/{id}/withdrawal` e `PATCH /processes/{id}/cancellation` são removidos.

**Rationale**: Um único verbo por intenção (excluir vs. arquivar) e autorização unificada (proponente efetivo OU perfil global Admin/BraCVAM) simplificam o contrato do front-end sem perder a distinção de quem pode agir sobre o quê — a distinção de ator agora vive na autorização e na trilha de auditoria (`user_id` vs. proponente efetivo), não em rotas separadas.

**Alternatives considered**: Manter `/withdrawal` e `/cancellation` como aliases finos do mesmo comando foi descartado — a spec pede explicitamente a eliminação desses dois endpoints, não apenas sua reimplementação interna.

## Autorização

**Decision**: `DELETE` usa `is_active_effective_proponent` (autorização local) OU `has_platform_wide_access` (autorização global, perfis `administrator`/`bracvam`) — ambas já existentes em `authorization.py`, sem alteração de assinatura. `PATCH .../archive` continua usando `has_process_review_access` (`triage.review`), respeitando conflito de interesse via `has_current_conflict`.

**Rationale**: Nenhuma das duas funções de autorização precisa de mudança; a feature não cria RBAC novo. Quem hoje detém `triage.review` além de Admin/BraCVAM é uma preocupação da Feature 023, não desta.

**Alternatives considered**: Fazer `DELETE` também aceitar `triage.review` foi descartado — o usuário especificou explicitamente proponente efetivo OU perfil global, não a permissão de revisão.

## Auditoria

**Decision**: Um único `event_type` novo, `PROCESS_DELETED`, cobre toda exclusão, independentemente do ator. `PROCESS_ARCHIVED` permanece como estava. Os eventos anteriores `PROCESS_CANCELLED` e `PROCESS_WITHDRAWN_BY_PROPONENT` deixam de ser produzidos por este fluxo.

**Rationale**: Decisão explícita do usuário (Clarification 2026-09-13, Q4): a distinção de ator fica implícita comparando `AuditEvent.user_id` com o proponente efetivo do processo, sem precisar de um tipo de evento por ator.

**Alternatives considered**: Manter dois `event_type` (um para o proponente, outro para Admin/BraCVAM) foi a recomendação original desta revisão, mas o usuário optou pela opção mais simples de um único tipo.

## Cancelamento em cascata e concorrência

**Decision**: Sem mudança em relação à versão anterior: carregar o processo alvo com bloqueio de linha (`with_for_update`), validar a ação, e marcar somente `Phase`, `ActivityInstance`, `ActivityRun`, `Task` e `EvaluationRun` ainda não terminais como `CANCELLED`, preservando itens já concluídos, formulários, artefatos, decisões e eventos.

**Rationale**: Essa lógica já existe e é reaproveitada integralmente pela exclusão unificada; o bloqueio de linha continua serializando comandos concorrentes sobre a mesma instância.

**Alternatives considered**: Nenhuma — este ponto não mudou com a revisão de 2026-09-13.

## Guardas para escrita e processamento assíncrono

**Decision**: Sem mudança: guarda de processo operacional nos serviços mutantes de formulário, submissão, triagem, tarefas e pré-avaliação; antes de rotear ou gravar resultado assíncrono, confirmar que o processo ainda existe e está em `AI_PRE_EVALUATION` quando aplicável.

**Rationale**: A guarda já cobre `CANCELLED` e `ARCHIVED` como estados bloqueadores; como a exclusão continua produzindo `CANCELLED`, nenhuma mudança adicional é necessária aqui.

**Alternatives considered**: Nenhuma — este ponto não mudou com a revisão de 2026-09-13.

## Demonstração e seed

**Decision**: Reduzir a demo e o seed de quatro para três cenários: exclusão pelo proponente efetivo, exclusão por Admin/BraCVAM de um processo de terceiro, e arquivamento de um processo terminal — mais uma tentativa bloqueada (excluir um processo já terminal ou arquivar um processo ainda ativo).

**Rationale**: Reflete os dois endpoints restantes e as duas vias de autorização de `DELETE`, atendendo ao `AGENTS.md` sem endpoint auxiliar ou dependência do núcleo.

**Alternatives considered**: Manter os quatro cenários antigos (rascunho, devolvida, ativo, terminal) misturaria estados que não afetam mais o resultado da operação, tornando a demo confusa sobre o que de fato mudou.

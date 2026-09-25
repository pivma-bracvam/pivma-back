# Phase 0 Research: Atribuição de Cargo por Convite com Link Compartilhável

A spec não deixou nenhum `[NEEDS CLARIFICATION]` em aberto (checklist 100% aprovado, três
rodadas de refinamento com o usuário). As decisões abaixo são de **técnica de
implementação**, não de produto — cada uma parte de um achado concreto no código atual.

## R1 — Token do convite: aleatório opaco + hash, não JWT

**Decision**: gerar o token com `secrets.token_urlsafe(32)` (stdlib, sem dependência nova),
devolver o valor bruto uma única vez na resposta de criação/reenvio, e persistir só o
`sha256` hexdigest dele (`hashlib.sha256`, stdlib) em `token_hash`. O aceite busca por
`token_hash = sha256(token_recebido)`.

**Rationale**: o projeto já usa dois mecanismos de segredo com propósitos diferentes —
`argon2-cffi` para senha (Spec 001, precisa resistir a força bruta sobre um segredo de
baixa entropia escolhido por humano) e `PyJWT` para sessão (`create_access_token`,
`src/pivma/core/security.py:27`, stateless, sem necessidade de revogar um token individual
antes do `exp`). O convite não se encaixa em nenhum dos dois: precisa ser **revogável**
antes do prazo (FR-013), o que um JWT stateless não permite sem uma lista de revogação
adicional — e não precisa da lentidão deliberada do Argon2id porque o segredo já nasce
com 256 bits de entropia (um SHA-256 já é caro o bastante para inviabilizar força bruta
sobre um valor aleatório desse tamanho; a lentidão do Argon2id existe para senhas
adivinháveis, não é o caso aqui). Guardar só o hash segue a mesma cautela já aplicada à
senha: um `pg_dump` da tabela não deve devolver um token utilizável.

**Alternatives considered**: reaproveitar `create_access_token`/JWT com um `exp` de 1h —
rejeitado porque FR-013 (revogar antes do prazo) exigiria uma denylist paralela, exatamente
o tipo de mecanismo duplicado que o Gate G1 do plano rejeita. Guardar o token em texto
plano — rejeitado pela mesma cautela já aplicada a senha (nunca guardar segredo em claro
quando um hash resolve com o mesmo custo de implementação).

## R2 — Um único registro mutável por convite, não um ciclo revogar+recriar

**Decision**: ao contrário de `Assignment` (Spec 006, que cria um novo ciclo a cada
designação para preservar histórico imutável de titularidade), o convite usa **uma única
linha mutável** por identidade (processo + papel + e-mail). Reenviar atualiza
`token_hash`/`expires_at` na mesma linha; a trilha de "quem reenviou quando" vive em
`AuditEvent` (`INVITE_RESENT`), não em linhas adicionais.

**Rationale**: a spec já resolveu isso explicitamente — FR-012 diz que o reenvio "preserva
o histórico do convite original" (identidade única), diferente de FR-... da Spec 006, que
fala em "outro ciclo" para designação. A diferença de fundo: um ciclo de `Assignment`
representa uma concessão de autoridade que precisa sobreviver como fato histórico
distinto (quem teve o cargo entre X e Y); um convite reenviado não é uma nova concessão,
é a mesma oferta com um prazo novo — o valor anterior de `token_hash`/`expires_at` não tem
significado de negócio próprio depois de superado, só a sequência de ações importa, e essa
sequência já fica completa em `AuditEvent`.

**Alternatives considered**: ciclo revogar+recriar como `Assignment` — rejeitado por
duplicar sem necessidade um padrão pensado para um problema diferente (titularidade
histórica), tornando a consulta "qual o convite pendente para X" uma agregação em vez de
uma leitura direta.

## R3 — Autorização por papel: uma função nova compõe três já existentes

**Decision**: `can_manage_role_assignment(session, user_id, process_id, role_key)` em
`core/authorization.py`:

```text
if can_manage_participants(...)          → True   # já existe, Spec 006: permissão global OU group_manager efetivo — cobre as 8 linhas
elif role_key in {sponsor, group_manager} and is_active_effective_proponent(...) → True   # única regra nova (FR-003)
else → False
```

**Rationale**: achado do próprio processo de spec — cruzando a tabela "papel × executor"
do usuário com o código, `is_effective_group_manager` (`authorization.py:344`) e
`is_active_effective_proponent` (`authorization.py:377`) já existem com exatamente a
semântica de "efetivo" que a matriz pede, e `can_manage_participants` (Spec 006) já cobre
sozinho as linhas 3–8 da tabela (Grupo Gestor e a permissão global que Admin/BraCVAM
sempre têm, Spec 023). A única lacuna real é o Proponente não ter hoje nenhuma autorização
de gestão de participantes — resolvida por uma cláusula adicional restrita a dois
`role_key`.

**Alternatives considered**: uma tabela de matriz configurável (papel → executor) no banco
— rejeitado por excesso de generalidade para uma regra que a spec já fixou por completo
(8 papéis, 3 grupos de executor); nada nesta feature pede que a matriz mude sem deploy.

## R4 — Fechamento da etapa: reaproveita o helper único da Spec 026, sem endpoint dedicado

**Decision**: nova função privada em `process_engine.py`,
`_maybe_close_role_assignment_activity(session, process, role_key, user_id)`, chamada ao
final da criação de designação (direta ou por aceite de convite):

1. Resolve, a partir de `template_version.definition_payload` (já em memória via o mesmo
   padrão de `_advance_dependent_activities`), a `ActivityInstance` do processo cujo
   `activity_type == 'role_assignment'` e `target_role_key == role_key` — campo novo do
   YAML, não uma coluna nova (ver `data-model.md`).
2. Se não achar (papel sem etapa declarada no template) ou já estiver `COMPLETED`, no-op.
3. Busca a execução atual via `get_current_activity_run` (`process_engine.py:810`, já
   existente — levanta `NotFoundError` se a atividade ainda não tiver execução, ou seja,
   ainda `BLOCKED`; tratado como no-op, não erro, porque uma designação direta pode
   preceder a atividade existir em processos antigos/sem o template atualizado).
4. Verifica FR-017: se existir algum `RoleAssignmentInvite` com `status='pending'` para
   esse `(process_id, role_key)`, não fecha.
5. Caso contrário, chama `_complete_activity_run` + `_advance_dependent_activities`
   (`process_engine.py:1855`/`1766`, ambas já genéricas e já usadas pelos quatro pontos
   unificados pela Spec 026).

**Rationale**: é exatamente o padrão que a Spec 026 deixou pronto — os dois pontos que já
concluem atividade (submissão, decisão de triagem) chamam esses dois helpers diretamente
do código de domínio, não por um endpoint "concluir atividade" genérico (confirmado por
grep: não existe tal endpoint hoje). Criar um agora só para isto duplicaria semântica sem
necessidade — a designação (ou o aceite do convite) já é o evento de domínio que fecha a
etapa.

**Alternatives considered**: endpoint `POST /activities/{id}/complete` genérico chamável
pelo frontend — rejeitado porque nenhuma outra atividade do roteiro tem isso hoje (a
conclusão é sempre efeito colateral de uma ação de domínio), e criar um só para esta
feature quebraria a consistência que a Spec 026 acabou de estabelecer.

## R5 — Campo novo no YAML (`target_role_key`), nenhuma coluna nova em `activity_instances`

**Decision**: a atividade `role_assignment` ganha um campo opcional a mais no YAML do
template, ao lado de `activity_type`:

```yaml
- key: "assign_sponsor"
  name: "Definir o Patrocinador"
  order_index: 1
  assigned_role: "proponent"        # já existe (Spec 018) — quem EXECUTA a atividade
  activity_type: "role_assignment"  # novo valor do campo já existente (Spec 017)
  target_role_key: "sponsor"        # novo — qual ParticipantRole esta atividade preenche
  dependencies: []
```

`assigned_role` (quem deve agir) e `target_role_key` (qual papel do processo é concedido)
são conceitos distintos e não podem colapsar em um só campo — confirmado durante a
elaboração da spec: para as linhas 1–2 da matriz, `assigned_role: "proponent"` mas
`target_role_key` é `sponsor` ou `group_manager`, nunca `proponent`.

**Rationale**: segue o mesmo padrão já estabelecido pela Spec 017 (`activity_type` é lido
de volta do `definition_payload` já congelado por versão, nunca persistido como coluna
extra por instância) — nenhuma migração em `activity_instances` é necessária, e a garantia
de imutabilidade por versão (Spec 004 FR-001/SC-002) já cobre `target_role_key` de graça,
do mesmo jeito que já cobre `activity_type`.

**Alternatives considered**: coluna `target_role_key` em `activity_instances` — rejeitado
por replicar, sem necessidade, um dado que o payload da versão já garante imutável e que
só é lido no momento de uma designação (não é um campo de leitura frequente em listagem,
que justificaria desnormalizar).

## R6 — Aceite do convite não toca no fluxo de cadastro/login (Spec 001/002)

**Decision**: `GET /invites/{token}` é público (sem autenticação) e só devolve dados de
pré-visualização (papel, processo, e-mail mascarado, validade) para a página do frontend
montar a tela "você foi convidado". `POST /invites/{token}/accept` exige sessão
autenticada (`CurrentUser`, mesmo mecanismo de cookie já existente) — a pessoa loga ou se
cadastra pelos endpoints **já existentes e inalterados** de Spec 001/002, e só depois o
frontend chama o aceite. O aceite compara o e-mail da sessão autenticada com o e-mail do
convite (FR-010) inteiramente no momento do aceite, sem qualquer alteração no cadastro em
si.

**Rationale**: minimiza a superfície de mudança — a spec já registra isso como Out of
Scope ("qualquer mudança no fluxo de cadastro público além do necessário para reconhecer
um e-mail de convite pendente"), e essa pesquisa confirma que **nenhuma mudança é
necessária**: comparar e-mails depois da autenticação, num endpoint novo e separado, cobre
o requisito sem tocar `routers/auth.py`. Reduz também o risco de regressão nos contratos
de Spec 001/002 que a spec explicitamente pede para preservar (SC-008 por analogia).

**Alternatives considered**: pré-preencher o formulário de cadastro com o e-mail do
convite (via querystring) — deixado como responsabilidade do frontend (detalhe de UX, não
de contrato de API) e fora do escopo desta pesquisa de backend.

## R7 — Expiração: campo novo em `Settings`, sem novo tipo de configuração

**Decision**: `INVITE_EXPIRATION_HOURS: int = Field(default=1)` em
`core/settings.py`, seguindo exatamente o padrão já usado por `ATTACHMENT_MAX_SIZE_MB`
(mesmo arquivo) — inteiro simples, lido de `.env`, com default seguro.

**Rationale**: nenhum padrão novo necessário; `pydantic-settings` já resolve isso pelo
`.env` do jeito que toda outra configuração de ambiente do projeto já usa.

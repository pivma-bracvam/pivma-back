# Phase 0 Research: Fechar Escalada de Privilégio (Issue #39, pós-clarify)

## 1. Escopo exato da remoção/adição em `can_manage_process_templates`

**Decision**: Adicionar `FORM_TEMPLATES_MANAGE = 'form_templates.manage'`
como constante em `core/authorization.py` (mesmo padrão de `RBAC_READ`,
`TRIAGE_REVIEW` etc.), e reescrever a função:

```python
async def can_manage_process_templates(session, user_id):
    profiles = await active_profiles_for_user(session, user_id)
    if any(p.system_key == ADMINISTRATOR_SYSTEM_KEY for p in profiles):
        return True
    return await has_permission(session, user_id, FORM_TEMPLATES_MANAGE)
```

**Rationale**: Remove as duas branches indevidas (`rbac.read`, nome de
perfil) e as substitui por uma checagem de permissão discreta, decidida na
sessão de clarificação (Opção B) — consistente com o padrão já usado para
`TRIAGE_REVIEW`/`AI_EVALUATIONS_MANAGE` no mesmo módulo.

**Alternatives considered**: `system_key in PLATFORM_WIDE_SYSTEM_KEYS`
(Opção A da clarificação) — rejeitada pelo usuário; teria a vantagem de não
precisar de migração, mas conflaria "ser BraCVAM" com "poder editar
formulário", perdendo granularidade e reabrindo o mesmo tipo de problema
desta issue (usar um critério grosso demais como proxy de autorização).

---

## 2. Escopo exato da remoção em `require_admin`

**Decision**: Idêntico ao plano anterior — remove só a branch de
`rbac.read`, sem adicionar `FORM_TEMPLATES_MANAGE` como critério válido
(spec, FR-003 e Assumptions: BraCVAM não pediu acesso a reprocessamento de
IA nem a streams de log).

**Rationale**: A permissão nova tem um propósito específico (edição de
formulário); estendê-la a `require_admin` ampliaria o escopo além do que a
clarificação pediu, sem necessidade de negócio demonstrada.

---

## 3. Migração Alembic para a permissão nova

**Decision**: Nova migração `fa506675d3f9_form_templates_manage_permission.py`,
`down_revision = '6ca4dd19c8fb'` (head atual em `develop`, confirmado
encadeando toda a cadeia de `migrations/versions/` — `deprecate_legacy_global_profiles`
é o último elo, nada referencia `6ca4dd19c8fb` como `down_revision`).
Segue **exatamente** o padrão de
`migrations/versions/d3f9a1c47b28_bracvam_profile_triage_permission.py`:

- `op.bulk_insert` em `permissions`: uma linha, `code='form_templates.manage'`.
- `op.bulk_insert` em `access_profile_permissions`: duas linhas, compondo a
  permissão nova a `BRACVAM_PROFILE_ID` e a `ADMIN_PROFILE_ID` (UUIDs
  canônicos já fixos: `...009` administrador, `...00a` bracvam — mesmos
  usados por `d3f9a1c47b28` e pelo `bootstrap_system.py` em progresso).
- `downgrade()` remove as composições e a permissão, no mesmo padrão de
  `DELETE` explícito por UUID literal usado na referência.

**Rationale**: É a única migração de referência no repositório que faz
exatamente este tipo de mudança (nova permissão + composição a perfis
existentes) — reutilizar o padrão byte a byte reduz risco e mantém
consistência de estilo para quem revisar.

**Alternatives considered**: Editar `bootstrap_system.py` (o script de
bootstrap idempotente que já lista `CANONICAL_PERMISSIONS`/
`PROFILE_PERMISSION_MAPPINGS`, incluindo `'bracvam': [...]`) — rejeitada
porque esse arquivo é WIP não commitado de outra feature (`specs/025-docs-migrations-seeds`,
alheia a esta issue), ainda não faz parte de `develop`. Editar um arquivo
que não existe na branch base (`fix/027-...`, criada a partir de `develop`)
não é uma opção real; a migração Alembic é o mecanismo real e já commitado
de evolução de schema/seed de RBAC neste projeto.

---

## 4. Teste de migração dedicado

**Achado**: O projeto tem um teste de migração dedicado para toda migração
de RBAC até agora — `tests/integration/migrations/test_bracvam_rbac_migration.py`
testa upgrade (`d3f9a1c47b28`) → downgrade (`8b701d7bfeae`, revisão
anterior) → upgrade (`head`) novamente, usando a infraestrutura compartilhada
de `test_secure_user_registration.py` (`migration_database`, `run_migration`,
`run_downgrade`).

**Decision**: Criar `tests/integration/migrations/test_form_templates_manage_migration.py`
seguindo exatamente esse padrão, com `PREVIOUS = '6ca4dd19c8fb'`.

---

## 5. Mapeamento completo dos consumidores afetados (reconfirmado)

Igual ao plano anterior — `can_manage_process_templates` tem 1 chamador
(`routers/processes.py:254`); `require_admin`/`AdminUser` (de
`pivma.dependencies`, não confundir com a schema homônima em
`pivma.schemas` usada por `routers/users.py`) tem 5 chamadores em
`admin_logs.py` e `pre_evaluation.py`. Nenhum muda de comportamento além do
já especificado.

---

## 6. Testes existentes que dependeriam do comportamento indevido

**Correção pós-implementação**: esta conclusão estava **errada**. Existe
`tests/unit/core/test_rbac_global_roles.py::test_bracvam_user_can_manage_process_templates`,
que cria a permissão `rbac.read` e afirma `can_manage_process_templates(...)
is True` para um usuário `bracvam` — ou seja, testava a própria brecha como
comportamento esperado. Não apareceu no grep de `research.md` original
porque o teste não menciona `rbac.read` no nome, só no corpo. Corrigido
trocando a permissão de prova para `form_templates.manage` (o critério
correto agora) — só a suíte completa (não o grep) revelou esse caso.

## 7. Mecanismo dinâmico de permissões (Spec 023) invalida a composição
   explícita planejada em T001

**Achado durante a implementação**: `core/authorization.py::effective_permission_codes`
já garante que Administrador e BraCVAM têm **toda** `Permission` ativa do
catálogo, mesmo sem `AccessProfilePermission` explícita — via
`has_platform_wide_access` → `_all_active_permission_codes`, com essa
intenção documentada no próprio docstring da função ("uma permissão nova
nunca precisa de uma migration adicional para alcançá-los"). A migração
planejada em `research.md` #3 (compor `form_templates.manage` explicitamente
a `bracvam`/`administrator`) era redundante e, pior, quebrava
`test_bracvam_rbac_migration.py`, que trava o conjunto **exato** de
composições explícitas do catálogo.

**Decision (revisada)**: a migração só insere a `Permission`
(`form_templates.manage`) no catálogo — sem nenhuma linha em
`access_profile_permissions`. Administrador e BraCVAM já a "têm"
dinamicamente a partir do momento em que ela existe no catálogo.

**Rationale**: Segue o padrão arquitetural já estabelecido pela Spec 023
para exatamente este caso (permissão nova alcançando os dois perfis
plataforma-wide), em vez de reintroduzir o padrão de composição explícita
de `d3f9a1c47b28` — que antecede a Spec 023 e ficou parcialmente obsoleto
por ela (a composição explícita de `triage.review` ao Administrador
continua no banco, mas hoje é redundante, não incorreta).

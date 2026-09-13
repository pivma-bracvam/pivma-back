# Pesquisa: Simplificação de Cargos Globais (RBAC)

## Concessão automática de permissões a Admin/BraCVAM

**Decision**: `effective_permission_codes(session, user_id)` e `active_profile_permissions(session, profile_id, *, system_key=None)` passam a checar, antes da consulta de composição, se o usuário/perfil é `administrator`/`bracvam` (`PLATFORM_WIDE_SYSTEM_KEYS`, já existente desde a Feature 018). Se for, retornam todo `Permission.code` ativo diretamente (`select(Permission.code).where(Permission.deleted_at.is_(None))`), sem passar pelo `JOIN` com `AccessProfilePermission`/`AccessProfile`/`UserAccessProfile`.

**Rationale**: como o conjunto é computado na consulta, toda `Permission` criada por uma migration futura já aparece automaticamente para Admin/BraCVAM, sem exigir uma migration de composição adicional (FR-002). É uma mudança pequena e local, concentrada nos dois pontos que já são a autoridade central de resolução de permissões — nenhuma rota individual precisa de lógica própria.

**Alternatives considered**: manter o modelo baseado em composição e (a) adicionar um gatilho de banco que replica automaticamente toda nova `Permission` para as composições de Admin/BraCVAM, ou (b) adotar a convenção de que toda migration que cria uma `Permission` também insere as duas composições. (a) adiciona uma peça de infraestrutura (trigger) para um problema que uma checagem de código resolve sem estado adicional; (b) é frágil — depende de alguém lembrar, exatamente o problema que a Spec 023 foi pedida para resolver.

## Descontinuação dos 8 perfis sem função

**Decision**: uma migration Alembic nova (`down_revision = 617f10506acc`, head atual) faz `UPDATE access_profiles SET deleted_at = now() WHERE system_key IN (...)` para os 8 `system_key`s (`management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`, `proponent`), e `UPDATE user_access_profiles SET deleted_at = now() WHERE profile_id IN (...) AND deleted_at IS NULL` para revogar qualquer atribuição ativa a eles.

**Rationale**: é o mesmo padrão de dados já usado pelas migrations que os criaram (`c1e4a9f8b312`, `d3f9a1c47b28`); soft-delete via `AuditMixin` preserva o histórico (`rbac_changes`, FR-004) sem remoção física. Nenhum desses 8 perfis tem `Permission` vinculada hoje (confirmado nas mesmas migrations), então a migration não precisa tocar `access_profile_permissions`.

**Alternatives considered**: remover fisicamente as linhas — rejeitado pela FR-004 (preservar histórico) e pelo padrão de soft-delete já usado em toda a base. Deixar os perfis ativos mas ocultá-los apenas na listagem da API — rejeitado porque ainda permitiria atribuí-los via `POST /rbac/users/{id}/profiles/{profile_id}`, contrariando FR-003/FR-007.

## `can_manage_process_templates` sem "Grupo Gestor"

**Decision**: remover `'Grupo Gestor'` do conjunto final `any(p.name in {...} for p in profiles)`, mantendo apenas `'Administrador'`. Nenhuma outra mudança na função.

**Rationale**: "Grupo Gestor" deixa de existir como perfil ativo, então essa branch nunca mais poderia ser satisfeita — removê-la é eliminar código morto, não uma mudança de comportamento observável. O caminho do meio da função (`has_permission(session, user_id, RBAC_READ)`) já cobre Administrador e BraCVAM automaticamente após a decisão anterior (RBAC_READ passa a fazer parte de "toda permissão" para os dois), preservando o acesso de ambos à gestão de templates sem precisar de um terceiro caminho.

**Alternatives considered**: reescrever a função inteira para depender só de `has_platform_wide_access` — rejeitado por ser uma mudança maior que o necessário (o caminho do meio já resolve Admin/BraCVAM); a única edição estritamente necessária é remover o nome que deixa de existir.

## "Padrão" como estado observável

**Decision**: nenhuma mudança de schema ou código. Um usuário sem `UserAccessProfile` ativo já aparece com `profiles: []` em `GET /users` (Spec 007) — esse é o sinal estável de "Padrão" exigido por FR-009.

**Rationale**: a Assumption da spec já registra que "Padrão" não é uma linha de `AccessProfile`; introduzir uma linha ou um campo novo só para representar "nenhum perfil" contradiria a própria definição do requisito e adicionaria um conceito sem necessidade demonstrada.

**Alternatives considered**: criar um `AccessProfile` literal chamado "Padrão" — rejeitado explicitamente pela spec (FR-009: "sem exigir um `AccessProfile` literal para esse estado").

## Contrato HTTP

**Decision**: nenhum endpoint novo, nenhuma mudança de schema de resposta. `GET /rbac/profiles` retorna menos itens (perfis descontinuados desaparecem da lista de fato porque a query filtra por `deleted_at`); o efetivo de permissões de Admin/BraCVAM (exposto onde `effective_permission_codes` já é usado) passa a incluir mais códigos. Nenhum `contracts/*.yaml` é necessário.

**Rationale**: a mudança é inteiramente de dados/regra de negócio, não de forma de interface.

## Impacto nos testes existentes

**Decision**: a suíte de testes cria schema via `table_registry.metadata.create_all` (ORM), não roda as migrations Alembic (`tests/conftest.py`, fixture `setup_database`) — os dados semeados pelas migrations de produção (incluindo os 8 perfis descontinuados) nunca existem no banco de teste. Fixtures como `non_triage_user` (`tests/conftest.py`, `system_key='management_group'`) criam seu próprio `AccessProfile` avulso via `_make_rbac_user`, independente da migration.

**Rationale/implicação**: a migration de descontinuação não quebra nenhum teste existente por si só (eles não dependem dos dados semeados). O que precisa de teste novo é a *regra* (Admin/BraCVAM têm toda permissão; os 8 `system_key`s não podem mais ser usados por uma migration futura sem revisão) e a migration em si (`tests/integration/migrations/`, no mesmo padrão de `test_bracvam_rbac_migration.py`).

**Alternatives considered**: nenhuma — é uma constatação sobre a infraestrutura de teste existente, não uma decisão de design desta feature.

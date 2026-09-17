# Phase 1 Data Model: Fechar Escalada de Privilégio (Issue #39, pós-clarify)

Uma linha de dado nova (permissão) e duas composições — nenhuma tabela,
coluna ou relacionamento novo. Schema inalterado; só dado novo em tabelas
já existentes, via migração Alembic.

## `Permission` (já existente, `permissions`)

| Campo | Valor da linha nova |
|---|---|
| `id` | `00000000-0000-0000-0000-00000000010d` — próximo da série `...01XX` já usada pelo catálogo canônico (`...101` a `...10c` já ocupados, confirmado em `bootstrap_system.py`/migrations existentes) |
| `code` | `form_templates.manage` |
| `description` | "Gerir a definição de formulários de processo (campos, nome, descrição)." |

## `AccessProfilePermission` (já existente, `access_profile_permissions`)

**Correção pós-implementação**: nenhuma linha nova aqui — achado durante a
implementação (`research.md` #7): `core/authorization.py::effective_permission_codes`
já garante dinamicamente que Administrador e BraCVAM têm **toda**
`Permission` ativa do catálogo, sem composição explícita
(`has_platform_wide_access` → `_all_active_permission_codes`, Spec 023).
Compor `form_templates.manage` explicitamente a esses dois perfis seria
redundante e quebraria o teste que trava o conjunto exato de composições
explícitas do catálogo (`test_bracvam_rbac_migration.py`). Basta a
`Permission` existir no catálogo — os dois perfis plataforma-wide já a
"têm" a partir daí.

## Sem novas relações, sem nova tabela

`AccessProfile`, `Permission` e `AccessProfilePermission` já têm o
relacionamento necessário (N:N via tabela de composição). Esta correção só
adiciona linhas — nenhuma migração de schema (`CREATE TABLE`/`ALTER TABLE`).

## Efeito sobre a lógica de autorização (não é dado, é código)

| Função | Antes | Depois |
|---|---|---|
| `can_manage_process_templates` | `system_key == 'administrator'` OU `rbac.read` OU `name == 'Administrador'` | `system_key == 'administrator'` OU `form_templates.manage` |
| `require_admin` | `system_key == 'administrator'` OU `rbac.read` | `system_key == 'administrator'` |

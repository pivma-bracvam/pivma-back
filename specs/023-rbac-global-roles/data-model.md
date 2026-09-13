# Modelo de Dados: Simplificação de Cargos Globais (RBAC)

Nenhuma tabela, coluna ou índice novo. Todas as entidades já existem desde a Feature 003 (`AccessProfile`, `Permission`, `AccessProfilePermission`, `UserAccessProfile`, `RbacChange`).

## AccessProfile

| Campo | Uso nesta feature |
|---|---|
| `system_key` | Após a migration, somente `administrator` e `bracvam` seguem ativos com `system_key` preenchido. Os 8 valores `management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`, `proponent` passam a existir apenas em linhas soft-deletadas (histórico). |
| `deleted_at` / `deleted_by` | Preenchidos pela migration para os 8 perfis descontinuados (`deleted_by` fica `NULL` — é uma mudança de dados feita pela migration, não por um ator humano identificável). |
| `name` | Como a unicidade de nome (`uq_access_profiles_name_ci_active`) é um índice parcial só sobre linhas ativas, o nome de um perfil descontinuado (ex.: "Grupo Gestor") volta a ficar disponível para um perfil **customizado** novo (`system_key=NULL`) criado via `POST /rbac/profiles` depois da migration. Esse perfil customizado não tem nenhuma permissão automática — é apenas uma coincidência de nome, sem efeito de autorização (ver Edge Cases no spec). |

### Perfis descontinuados (linhas afetadas pela migration)

| `system_key` | Nome | Permissões vinculadas hoje |
|---|---|---|
| `proponent` | Proponente | nenhuma |
| `management_group` | Grupo Gestor | nenhuma (mas reconhecido por nome em `can_manage_process_templates`, ajustado nesta feature) |
| `study_manager` | Gerente do Estudo | nenhuma |
| `participating_laboratory` | Laboratório Participante | nenhuma |
| `ad_hoc_evaluator` | Avaliador Ad Hoc | nenhuma |
| `reviewer` | Revisor | nenhuma |
| `specialist` | Especialista | nenhuma |
| `statistical_analyst` | Analista Estatístico | nenhuma |

## Permission

Sem mudança estrutural. A partir desta feature, toda `Permission` ativa é considerada automaticamente concedida a `administrator`/`bracvam` na resolução de permissões efetivas — não por uma linha em `AccessProfilePermission`, mas pela lógica de `effective_permission_codes`/`active_profile_permissions` (ver `research.md`). As composições já existentes (`rbac.read`, `rbac.profiles.manage`, `rbac.assignments.manage`, `triage.review` para `administrator`; `triage.review`, `ai_evaluations.read`, `ai_evaluations.manage` para `bracvam`) permanecem no banco sem necessidade de remoção — ficam redundantes, mas inofensivas.

## UserAccessProfile

Qualquer linha ativa (`deleted_at IS NULL`) cujo `profile_id` aponte para um dos 8 perfis descontinuados é soft-deletada pela migration. Nenhuma outra linha é tocada.

## RbacChange

Não é alterado. O histórico de mudanças anteriores (criação dos perfis, composições) permanece consultável via `GET /rbac/changes` sem modificação.

## Resolução de permissões efetivas (comportamento, não estrutura)

| Usuário tem perfil... | `effective_permission_codes` retorna |
|---|---|
| `administrator` ou `bracvam` (ativo) | Todo `Permission.code` ativo no sistema, presente e futuro. |
| Qualquer outro perfil customizado (`system_key=NULL`) | Como hoje: união das permissões compostas nos perfis ativos do usuário. |
| Nenhum perfil ativo ("Padrão") | Lista vazia — como hoje. |

## Papéis locais por processo (fora do escopo, citado para clareza)

`Assignment.role_key` / `ActivityCargo` (Feature 018) não são `AccessProfile` e não são tocados por esta feature, mesmo quando o nome coincide (`study_manager`, `participating_laboratory`, `ad_hoc_evaluator` existem também como papel local, em `assignments`, tabela e mecanismo diferentes).

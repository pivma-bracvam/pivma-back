# Quickstart: Validar o Fechamento da Escalada de Privilégio

**Feature**: 027-template-authz-escalation

Sem demo nova (AGENTS.md, Regra 1). Reaproveita `demos/forms/index.html`
(edição de template) e `demos/operational-index/index.html` (logs
administrativos), ambas já conectadas à API real.

## Pré-requisitos

- API rodando localmente (`poe serve`), **com a migração nova aplicada**
  (`alembic upgrade head` — cria a permissão `form_templates.manage` e a
  concede aos perfis `bracvam` e `administrator`).
- Um usuário com o perfil oficial de Administrador.
- Um usuário com o perfil `bracvam` canônico (passa a ter
  `form_templates.manage` automaticamente após a migração).
- Um usuário de teste com um perfil customizado que só conceda `rbac.read`
  (para reproduzir o bug antes da correção / confirmar que continua
  recusado depois).

## Passos

1. Autenticado como o usuário só-`rbac.read`, chamar `PUT
   /processes/templates/{key}/forms/{form_key}` → **antes da correção**: 200
   (bug); **depois**: 403.
2. Com o mesmo usuário, chamar `GET /admin/logs/operational`, `GET
   /admin/logs/ai` e `POST /pre-evaluations/{run_id}/retry` → **antes**: 200/202
   (bug); **depois**: 403 nos três.
3. Criar (via banco, em ambiente local) um perfil customizado com `name =
   "Administrador"` e `system_key = null`, atribuir a um usuário sem
   nenhuma outra permissão, e repetir o passo 1 → **antes**: 200 (bug);
   **depois**: 403.
4. Autenticado como o usuário com o perfil `bracvam` canônico, chamar `PUT
   /processes/templates/{key}/forms/{form_key}` com uma edição de campo
   legítima → **antes da migração**: 403 (gap de negócio real); **depois**:
   200 — esta é a capacidade que a correção precisa preservar, não só a
   parte de bloqueio.
5. Repetir os passos 1-2 autenticado como o usuário com o perfil oficial de
   Administrador → deve continuar 200/202/200 em todos, sem regressão.
6. Abrir `demos/forms/index.html` autenticado como um usuário `bracvam` e
   confirmar que a edição de um template continua funcionando normalmente
   pela interface — não só administrador.
7. Abrir `demos/operational-index/index.html` autenticado como o
   administrador oficial e confirmar que os streams/históricos de log
   continuam carregando normalmente.

## Resultado esperado

Passos 1-3 têm resultado novo (403 onde antes havia sucesso — a
vulnerabilidade fechada). Passo 4 tem resultado novo na direção oposta (200
onde antes seria incorretamente 403 se a correção só bloqueasse sem
preservar a necessidade do BraCVAM) — é a evidência de que a correção não
introduziu uma regressão funcional. Passos 5-7 comprovam ausência de
regressão para quem já era legitimamente autorizado.

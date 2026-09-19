# Implementation Plan: Fechar Escalada de Privilégio em Templates e Endpoints Administrativos (Issue #39)

**Branch**: `fix/027-template-authz-escalation` | **Date**: 2026-09-17 (revisão pós-`/speckit-clarify`) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-template-authz-escalation/spec.md`

## Summary

Duas funções de autorização (`can_manage_process_templates` em
`core/authorization.py:632-644` e `require_admin` em
`dependencies.py:104-124`) tratam a permissão `rbac.read` como se fosse
prova de privilégio administrativo, e a primeira também aceita qualquer
perfil cujo **nome de exibição** seja literalmente `"Administrador"`,
independente do `system_key`.

A correção inicialmente prevista (restringir as duas funções a `system_key
== 'administrator'`) foi revista na sessão de `/speckit-clarify`: a equipe
BraCVAM tem uma necessidade de negócio real de editar formulários
(adicionar/ajustar campos) que, hoje, só é satisfeita através da própria
brecha — o perfil `bracvam` canônico não tem nenhuma permissão de template.
A correção final:

1. Cria a permissão `form_templates.manage` (migration Alembic, seguindo o
   padrão já usado por `d3f9a1c47b28_bracvam_profile_triage_permission.py`)
   e a concede aos perfis canônicos `bracvam` e `administrator`.
2. `can_manage_process_templates` passa a aceitar `system_key ==
   'administrator'` **ou** a permissão `form_templates.manage` — removendo
   `rbac.read` e a checagem por nome como critérios.
3. `require_admin` passa a aceitar só `system_key == 'administrator'` —
   removendo `rbac.read` como critério, sem adicionar a permissão nova (o
   BraCVAM não pediu acesso a reprocessamento de IA nem a streams de log).

Nenhuma auditoria/migração de contas reais é necessária (decisão da sessão
de clarificação: o ambiente é recriado do zero neste estágio do projeto).

## Technical Context

**Language/Version**: Python 3.14 (`pyproject.toml`, `requires-python = ">=3.14,<4.0"`)

**Primary Dependencies**: FastAPI 0.141, SQLAlchemy 2.0 (async), Alembic — nenhuma dependência nova

**Storage**: PostgreSQL; **uma migração Alembic nova** (diferente da versão anterior deste plano) — insere 1 `Permission` e 2 `AccessProfilePermission` (composição para `bracvam` e `administrator`), no mesmo padrão de `migrations/versions/d3f9a1c47b28_bracvam_profile_triage_permission.py`. `down_revision` encadeia a partir do head atual em `develop`, `6ca4dd19c8fb` (`deprecate_legacy_global_profiles`).

**Testing**: pytest + pytest-asyncio, metodologia já usada no projeto; skill `fastapi-testing-methodology` carregada explicitamente antes de tocar em teste. A suíte de testes usa Postgres efêmero via testcontainers (`tests/conftest.py`), que aplica `create_all` do zero — a migração nova não precisa de teste de migração dedicado tipo `tests/integration/migrations/` (que testam upgrade/downgrade sobre uma base pré-existente) a menos que o padrão do projeto exija; verificar em `/speckit-tasks` se as migrations de RBAC anteriores têm teste dedicado e seguir o mesmo padrão.

**Target Platform**: Linux server (backend FastAPI já containerizado)

**Project Type**: Serviço web único (backend); `demos/forms/` e `demos/operational-index/` são as interfaces desacopladas já existentes para os dois pontos afetados

**Performance Goals**: Nenhuma meta nova — mesmo número de consultas ao banco por requisição (`active_profiles_for_user`/`has_permission` já eram chamadas hoje).

**Constraints**: Nenhum endpoint novo, nenhuma mudança de schema de resposta (AGENTS.md, Regra 4); `require_admin` não recebe a permissão nova (só `can_manage_process_templates`); `ADMINISTRATIVE_PERMISSIONS`/`ensure_administrator_remains` não são tocados nem incluem a permissão nova (spec, Assumptions).

**Scale/Scope**: Duas funções de autorização, uma migração Alembic nova (1 permissão + 2 composições), 1 endpoint de mutação de template + 5 endpoints administrativos como consumidores indiretos, testes de regressão em 3+ arquivos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Nota**: `.specify/memory/constitution.md` contém só o template padrão (não
ratificado). O gate usa os princípios registrados em `AGENTS.md` (lido de
`git show HEAD:AGENTS.md`, já que a cópia no working tree segue vazia por
uma edição não commitada e alheia a esta feature).

**Pré-design: APROVADO**

- **Regra 1 (demo por novo módulo)**: não se aplica.
- **Regra 3 (demonstração como critério de conclusão)**: em conformidade —
  `demos/forms/index.html` e `demos/operational-index/index.html` já
  existem e validam contra a API real; nenhuma demo nova necessária.
- **Regra 4 (proibição de endpoints facilitadores)**: em conformidade —
  nenhum endpoint novo.
- **Menor implementação completa**: em conformidade — a migração segue
  exatamente o padrão já estabelecido por `d3f9a1c47b28` para adicionar uma
  permissão e compô-la a perfis existentes; nenhuma tabela ou mecanismo
  novo.

**Pós-design: APROVADO**

- `data-model.md` confirma: nenhuma tabela/coluna nova, só 1 linha de
  `Permission` + 2 de `AccessProfilePermission`, inseridas por migração —
  mesma categoria de mudança que `d3f9a1c47b28` já fez.
- `research.md` #3-#4 encontraram e seguiram o padrão exato já estabelecido
  no repositório para este tipo de migração (RBAC: nova permissão + teste
  de upgrade/downgrade dedicado), evitando inventar um mecanismo novo.
- `contracts/` permanece vazio deliberadamente — nenhum contrato muda de
  forma (SC-004).
- Nenhum item pendente em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/027-template-authz-escalation/
├── plan.md              # Este arquivo (revisado pós-clarify)
├── research.md          # Fase 0 — decisões da correção + da migração
├── data-model.md        # Fase 1 — nova Permission e composições
├── quickstart.md        # Fase 1 — validação manual via demos existentes
├── contracts/           # Vazio deliberadamente — ver "Contracts" abaixo
└── tasks.md             # Saída do /speckit-tasks (não criado por este comando)
```

### Source Code (repository root)

```text
migrations/versions/
└── <novo_revision>_form_templates_manage_permission.py  # Permission +
    # composição (bracvam, administrator); down_revision = 6ca4dd19c8fb

src/pivma/core/authorization.py
├── FORM_TEMPLATES_MANAGE = 'form_templates.manage'  # nova constante,
│                                                       mesmo padrão de RBAC_READ etc.
└── can_manage_process_templates()  # remove rbac.read e name=='Administrador';
                                      # adiciona has_permission(FORM_TEMPLATES_MANAGE)

src/pivma/dependencies.py
└── require_admin()  # remove só a branch de rbac.read

tests/
├── api/routers/test_process_template_editor.py   # + regressão: rbac.read,
│                                                    perfil "Administrador" falso,
│                                                    e form_templates.manage (novo caminho)
├── integration/test_admin_logs_sse.py             # + regressão: rbac.read recusado
├── api/routers/test_pre_evaluation_*.py (ou novo)  # + regressão: retry recusado
│                                                     para rbac.read e para
│                                                     form_templates.manage isolado
└── integration/migrations/ (se o padrão do projeto exigir)  # teste da migração nova
```

**Structure Decision**: Mudança confinada a duas funções, uma migração nova
e os testes que exercitam os pontos afetados — nenhum diretório novo em
`src/`, nenhum demo/seed novo.

## Contracts

Este projeto expõe uma API REST, mas esta correção não adiciona, remove nem
muda a forma de nenhum endpoint, request ou response schema (spec, SC-004) —
só estreita/amplia (conforme o caso) quem passa na autorização de endpoints
já existentes, e adiciona uma linha de dado ao catálogo de permissões (não
um contrato). `contracts/` fica deliberadamente vazio.

## Complexity Tracking

> Nenhuma violação do Constitution Check a justificar. A migração nova é a
> mesma categoria de mudança que `d3f9a1c47b28` já fez para o mesmo perfil
> (`bracvam`) — não introduz mecanismo, tabela ou padrão novo de RBAC.

# Implementation Plan: Simplificação de Cargos Globais (RBAC)

**Branch**: `023-rbac-global-roles` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-rbac-global-roles/spec.md`

## Summary

Reduzir os perfis globais atribuíveis a exatamente três: Padrão (nenhum `AccessProfile` ativo), Administrador e BraCVAM. Administrador e BraCVAM passam a ter, de forma dinâmica, toda `Permission` ativa do sistema — presente e futura — sem exigir migration de composição por permissão nova. Os outros 8 perfis globais hoje semeados (`management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`, `proponent`), que não têm nenhuma `Permission` vinculada hoje, são descontinuados via migration (soft-delete), junto com qualquer `UserAccessProfile` ativo que os referencie. O único ponto de código que reconhecia um perfil global pelo nome fora do sistema de permissões (`can_manage_process_templates`, que checava "Grupo Gestor") é ajustado. Papéis locais por processo (`Assignment.role_key`/`ActivityCargo`, Feature 018) não são tocados.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy async 2, Alembic

**Storage**: PostgreSQL (tabelas `access_profiles`, `permissions`, `access_profile_permissions`, `user_access_profiles`, `rbac_changes` — todas já existentes desde a Feature 003)

**Testing**: pytest, pytest-asyncio, factory_boy, testcontainers

**Target Platform**: Serviço web FastAPI em Linux

**Project Type**: Serviço web monolítico

**Performance Goals**: Nenhuma mudança de perfil de performance; a leitura de permissões efetivas de Admin/BraCVAM passa a ser um `SELECT` simples sobre `permissions` (sem os quatro `JOIN`s da composição), o que é uma consulta mais barata que a atual.

**Constraints**: Não alterar `Assignment`, `ActivityCargo` ou qualquer papel local por processo (Feature 018). Não remover fisicamente nenhuma linha de `access_profiles`/`user_access_profiles` — apenas soft-delete, preservando `rbac_changes`. Não introduzir tabela, coluna ou permissão nova.

**Scale/Scope**: Uma migration Alembic; duas funções de `core/authorization.py` alteradas (`effective_permission_codes`, `active_profile_permissions`); uma função ajustada (`can_manage_process_templates`); nenhuma rota nova.

## Constitution Check

**Nota**: `.specify/memory/constitution.md` ainda contém somente o template padrão (não ratificado — ver AGENTS.md). O gate abaixo usa os princípios registrados em `AGENTS.md`.

**Pré-design: APROVADO**

- Toda decisão de domínio (quais 3 perfis permanecem, Admin/BraCVAM com tudo, os outros 8 descontinuados) foi confirmada pelo responsável da demanda e fundamentada em leitura direta das migrations existentes (`c1e4a9f8b312`, `d3f9a1c47b28`) antes da especificação — não há inferência não identificada como tal.
- A mudança fica restrita ao RBAC global (`AccessProfile`/`Permission`); papéis locais por processo (Feature 018) e o restante do domínio de processos (Spec 022) não são tocados, exceto pela formalização de uma pré-condição já verdadeira hoje.
- Auditoria: a descontinuação preserva `rbac_changes` e usa soft-delete (`AuditMixin`), nunca remoção física.
- Autorização permanece verificada no backend: a concessão dinâmica de permissões a Admin/BraCVAM é resolvida em `effective_permission_codes`/`has_permission`, os pontos centrais já usados por toda a aplicação — nenhuma rota individual precisa de lógica própria.
- Nenhuma dependência, tabela ou endpoint novo é introduzido.

**Pós-design: APROVADO**

O desenho reaproveita a distinção `PLATFORM_WIDE_SYSTEM_KEYS` (`administrator`/`bracvam`) já existente desde a Feature 018, aplicando-a também à resolução de permissões efetivas — não cria um mecanismo paralelo. A descontinuação dos 8 perfis é uma migration de dados no mesmo padrão das migrations `c1e4a9f8b312`/`d3f9a1c47b28` que os criaram. Nenhum contrato HTTP muda de forma; apenas os dados retornados mudam (menos perfis listados, mais permissões efetivas para Admin/BraCVAM).

## Project Structure

### Documentation (this feature)

```text
specs/023-rbac-global-roles/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md                     # gerado por /speckit-tasks
```

Sem `contracts/`: nenhum endpoint novo é criado e nenhum contrato HTTP existente muda de forma (`GET /rbac/profiles`, `GET /rbac/users/{id}` continuam com o mesmo schema de resposta — apenas os dados mudam).

### Source Code

```text
src/pivma/
└── core/
    └── authorization.py    # effective_permission_codes, active_profile_permissions,
                             # can_manage_process_templates

migrations/versions/
└── <nova>_deprecate_legacy_global_profiles.py   # down_revision = 617f10506acc (head atual)

tests/
├── unit/core/            # regra de "toda permissão" para Admin/BraCVAM
├── api/routers/          # GET /rbac/profiles, efetivo de permissões, template management
└── integration/migrations/  # aplica a nova migration e confere soft-delete + preservação de rbac_changes
```

**Structure Decision**: A lógica de autorização já está centralizada em `core/authorization.py` (Feature 003/014/018); esta feature estende as duas funções que hoje resolvem permissões (`effective_permission_codes`, `active_profile_permissions`) em vez de criar um módulo novo. A descontinuação de dados é uma migration, no mesmo diretório e padrão das que criaram os perfis originalmente.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional requer justificativa.

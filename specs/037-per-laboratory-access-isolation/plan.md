# Implementation Plan: Isolamento de acesso por laboratório

**Branch**: `feat/037-per-laboratory-access-isolation` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/037-per-laboratory-access-isolation/spec.md`

## Summary

A Spec 036 já filtra tarefas e linha do tempo por laboratório. Esta feature
fecha o que falta da issue #59:

1. `require_laboratory_run_access` ganha o nível `view` e passa a responder
   "não encontrado" para a execução de outro laboratório, com a mesma
   mensagem de execução inexistente (R2).
2. Um predicado único, `is_process_manager`, define a gestão do processo
   (Admin, BraCVAM, `group_manager` efetivo). A linha do tempo, as rotas de
   dispensa e reabertura e a verificação de execução passam a usá-lo (R1).
3. Testes cobrem a matriz de perfis por operação e a regra de uma designação
   de participante por usuário no processo, que o índice único já garante
   (R3).
4. O README ganha as regras na seção de permissões.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2.
Nenhuma dependência nova.

**Storage**: PostgreSQL 17. Nenhuma migração.

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy,
`TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`.

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: sem mudança. A verificação de execução faz no
máximo três consultas curtas, como hoje.

**Constraints**:
- Nenhuma expectativa da suíte da Spec 036 muda, exceto o tipo de erro de
  "laboratório A conclui a execução de B" (403 → 404, FR-001).
- Nenhuma rota nova.

**Scale/Scope**:
- `authorization.py`: 1 predicado novo.
- `process_engine.py`: `require_laboratory_run_access` alterada,
  `complete_laboratory_run` usa a mensagem única.
- `routers/processes.py` e `routers/laboratory_runs.py`: trocam a dupla
  verificação pelo predicado.
- 2 arquivos de teste novos, 1 ajustado, fábrica com `template` opcional.
- README.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` é o template sem preencher, como nas
specs 031 a 036. Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Issue #59; Plano de Trabalho (módulo de ensaios interlaboratoriais); RF044, RF050; Spec 030, 035 e 036 |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ 4 decisões em Clarifications |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ A mudança só restringe: 403 vira 404 para quem não vê a execução. Nenhuma permissão nova |
| Mudança cirúrgica, sem abstração preventiva | ✅ Sem rota nova; FR-008 reaproveita o índice único existente (R3) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final do `tasks.md` |

**Re-check pós-design**: sem violações.

## Project Structure

### Documentation (this feature)

```text
specs/037-per-laboratory-access-isolation/
├── plan.md
├── research.md          # R1–R4
├── data-model.md        # matriz de acesso (sem entidade nova)
├── quickstart.md
├── contracts/
│   └── access-matrix.md # respostas por perfil e operação
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py     # is_process_manager (novo)
│   └── process_engine.py    # require_laboratory_run_access(level), LABORATORY_RUN_NOT_FOUND
└── routers/
    ├── processes.py         # _events_of_visible_laboratories usa is_process_manager
    └── laboratory_runs.py   # _require_process_manager usa is_process_manager

tests/
├── factories/laboratory_run_factory.py                 # frozen_lab_process(template=...)
├── integration/database/test_laboratory_run_access.py  # 403 → 404 entre laboratórios
├── integration/database/test_laboratory_access_matrix.py  # novo: ler/concluir por perfil
└── api/routers/test_laboratory_access_matrix.py        # novo: /tasks, /tasks/{id}, linha do tempo, designação dupla

README.md                    # seção de permissões
```

**Structure Decision**: a regra fica no motor, ao lado de
`require_activity_access`, que as rotas das issues #28 a #31 já vão chamar.

## Complexity Tracking

Sem violações dos gates.

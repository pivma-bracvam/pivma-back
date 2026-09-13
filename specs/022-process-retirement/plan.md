# Implementation Plan: Exclusão (Soft-Delete) e Arquivamento de Processos

**Branch**: `022-process-retirement` | **Date**: 2026-09-13 (revisão pós-`/speckit-clarify`) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-process-retirement/spec.md`

## Summary

Reduzir o ciclo de vida a dois contratos REST: `DELETE /processes/{id}` (soft-delete universal) e `PATCH /processes/{id}/archive`. `DELETE` é aceito em qualquer estado não-terminal, para o proponente efetivo (autorização local) ou para um usuário com perfil global Administrador/BraCVAM (autorização global), sem exigir ausência de submissão formal. Ele reaproveita a cascata de cancelamento já existente (`_cancel_process_locked`), define `process.status = CANCELLED`, preenche `deleted_at`/`deleted_by` via `AuditMixin` e preserva os documentos em `ATTACHMENTS_DIR/{process_id}/` — a remoção física deixa de existir. `PATCH .../archive` continua exigindo `triage.review`, sem conflito de interesse, e aceita `CLOSED` ou `CANCELLED` (incluindo um `CANCELLED` produzido pela exclusão). Um filtro de leitura global (`do_orm_execute` + `with_loader_criteria` em `database/__init__.py`) passa a ocultar por padrão qualquer entidade `AuditMixin` soft-deletada em todo o sistema, com bypass explícito via `execution_options(skip_soft_delete_filter=True)`. Os endpoints `/withdrawal` e `/cancellation` são removidos. A simplificação da matriz de cargos globais (Padrão/Admin/BraCVAM) é uma dependência externa (Feature 023) e não faz parte desta implementação.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy async 2, Alembic

**Storage**: PostgreSQL e diretório local de anexos

**Testing**: pytest, pytest-asyncio, factory_boy, testcontainers; Ruff para lint

**Target Platform**: Serviço web FastAPI em Linux; demonstrações estáticas servidas pelo projeto e conectadas à API local

**Project Type**: Serviço web monolítico, com páginas HTML/JavaScript desacopladas em `demos/`

**Performance Goals**: Uma ação de ciclo de vida atualiza somente o processo e as entidades subordinadas afetadas em uma transação. Nenhuma ação remove arquivos do disco. Listagens operacionais mantêm a paginação atual e não consultam arquivados nem excluídos por padrão — o filtro de soft-delete é aplicado uma vez, no nível de sessão, em vez de repetido por rota.

**Constraints**: Reutilizar RBAC e auditoria existentes (`is_active_effective_proponent`, `has_platform_wide_access`, `has_process_review_access`); não criar nenhuma permissão ou perfil novo (a simplificação de cargos é a Feature 023, fora desta entrega); não introduzir restauração, exclusão física, novos perfis, endpoints de apoio à demo ou uma máquina de estados paralela; preservar todos os documentos em disco em qualquer exclusão. Toda mutação e conclusão assíncrona deve respeitar `CANCELLED` e `ARCHIVED`. O filtro global de soft-delete cobre toda entidade `AuditMixin` do sistema (decisão explícita do responsável da demanda — Clarification 2026-09-13, Q5), não apenas `ProcessInstance`.

**Scale/Scope**: Uma instância de processo por comando; duas operações de ciclo de vida (`DELETE`, `ARCHIVE`); router de processos, motor de processo, pré-avaliação assíncrona, schemas, testes, seed, demo e a camada de sessão do banco (`core/database/__init__.py`).

## Constitution Check

**Nota**: `.specify/memory/constitution.md` ainda contém somente o template padrão (não ratificado — ver AGENTS.md). O gate abaixo usa os princípios registrados em `AGENTS.md` (classificação de fontes, autorização no backend, menor implementação completa, proibição de escopo não demonstrado) como critério de aprovação.

**Pré-design: APROVADO**

- A redução de quatro para dois endpoints e a unificação de `DELETE_DRAFT`/`WITHDRAW`/`CANCEL` em um único `DELETE` foram decididas e registradas na sessão de clarificação de 2026-09-13, com justificativa explícita (reaproveitamento de `_cancel_process_locked`, ver [research.md](research.md)).
- A autorização de `DELETE` reaproveita duas funções já existentes (`is_active_effective_proponent`, `has_platform_wide_access`) — nenhuma permissão, perfil ou tabela nova é criada por esta feature.
- A simplificação da matriz de cargos globais foi deliberadamente excluída deste escopo e registrada como dependência externa (Feature 023), evitando o redesenho de RBAC que a spec já classificava como fora de escopo.
- Auditoria: cada exclusão e cada arquivamento gera um evento imutável (`PROCESS_DELETED`, `PROCESS_ARCHIVED`) com ator, estado anterior/resultante e momento.
- **Exceção sinalizada e aprovada pelo usuário**: o filtro global de soft-delete (`do_orm_execute`/`with_loader_criteria` sobre todo `AuditMixin`) extrapola o raio de impacto usual de uma feature de ciclo de vida de processos, alterando o comportamento de leitura de todo o sistema. Isso foi explicitamente sinalizado ao usuário como risco (Clarification 2026-09-13, Q5, recomendação B — escopo restrito a `ProcessInstance`) e ele optou conscientemente pela Opção A (escopo global). Ver Complexity Tracking.

**Pós-design: APROVADO**

O desenho reaproveita status, colunas de auditoria e funções de autorização já existentes; nenhuma tabela, coluna ou permissão nova é criada. A exclusão troca remoção física por soft-delete (`deleted_at`/`deleted_by`), preservando o agregado e os anexos. Os dois endpoints restantes tornam a intenção inequívoca, e as guardas ficam no domínio e no worker, não somente na interface HTTP. O único item fora do padrão "menor mudança possível" é o filtro global de sessão, explicitamente aprovado pelo usuário e registrado em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/022-process-retirement/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── process-lifecycle.openapi.yaml
└── tasks.md                     # regenerado por /speckit-tasks
```

### Source Code

```text
src/pivma/
├── core/
│   ├── authorization.py          # is_active_effective_proponent, has_platform_wide_access, has_process_review_access — reutilizados sem alteração de assinatura
│   ├── database/
│   │   ├── models.py             # entidades persistidas existentes; nenhuma coluna nova
│   │   └── __init__.py           # NOVO: listener do_orm_execute + with_loader_criteria(AuditMixin) e execution_options(skip_soft_delete_filter)
│   ├── process_engine.py         # unifica DELETE_DRAFT/WITHDRAW/CANCEL em um único comando de exclusão; remove a guarda de submissão formal; para de remover anexos
│   ├── attachment_service.py     # deixa de ser chamado pelo comando de ciclo de vida (documentos nunca mais são removidos por exclusão)
│   └── pre_evaluation_service.py # proteção contra conclusão tardia (sem alteração de contrato)
├── routers/
│   └── processes.py              # remove as rotas /withdrawal e /cancellation; contrato HTTP e consulta histórica de ARCHIVED
└── schemas.py                    # request/response de ciclo de vida com available_actions restrito a DELETE/ARCHIVE

tests/
├── api/routers/                  # contrato, autorização (proponente e admin/bracvam), listagem e fluxos
├── unit/core/                    # regras puras e de domínio (available_actions com 2 códigos)
├── integration/ai/               # execução tardia de pré-avaliação
└── integration/database/         # soft-delete, preservação de anexos, concorrência e filtro global

scripts/seeds/
└── seed_process_retirement.py    # ajustado para os dois cenários de exclusão (proponente e admin/bracvam) e o de arquivamento

demos/
├── process-retirement/
│   └── index.html                # ajustado para os dois botões (excluir/arquivar)
└── index.html
```

**Structure Decision**: O backend existente concentra regras em `core/process_engine.py` e os contratos HTTP em `routers/` e `schemas.py`. A única adição estrutural é `core/database/__init__.py`, que passa a hospedar o listener de sessão do soft-delete — decisão do usuário de que essa infraestrutura pertence à camada de banco, não ao motor de processo. A demonstração permanece descartável em `demos/` e usa somente os contratos públicos descritos nesta feature.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada |
|---|---|---|
| Filtro de soft-delete aplicado globalmente a todo `AuditMixin`, e não apenas a `ProcessInstance` | Decisão explícita do usuário (Clarification 2026-09-13, Q5): quer a rede de segurança de leitura para toda entidade soft-deletável do sistema, não só processos, para evitar esquecer o filtro manual em rotas futuras. | Escopo restrito a `ProcessInstance` (recomendação original desta revisão) — rejeitado pelo usuário por reduzir o valor da rede de segurança para o restante do sistema. |

**Consequência real, não apenas teórica**: rodar a suíte completa do repositório (não só os testes da 022) revelou 11 falhas em 3 specs sem relação com processos — `institutional.py` (consulta por id que mostra registro inativo), `users.py` (`GET /users?active=false`) e um `outerjoin` em `authorization.py` que, combinado ao filtro global, produzia **resultado errado** (não apenas vazio) para afiliação institucional. As quatro consultas afetadas foram corrigidas com `execution_options(skip_soft_delete_filter=True)` (ver `tasks.md`, Phase 7). Isso confirma, com dados, o risco que a recomendação original (escopo restrito) pretendia evitar; o usuário foi informado do resultado concreto e optou por manter o escopo global e corrigir os pontos encontrados, em vez de restringir o filtro. **Risco residual**: a correção foi guiada pelos testes que falharam, não por uma auditoria exaustiva de toda consulta a entidades `AuditMixin` no repositório — pode haver outras rotas com o mesmo padrão ("mostrar registro inativo por id") em código sem teste equivalente, que ficariam quebradas em produção sem nenhum teste acusando.

Nenhuma outra violação constitucional ou complexidade adicional requer justificativa.

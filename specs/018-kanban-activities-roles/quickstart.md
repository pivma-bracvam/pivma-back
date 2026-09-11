# Quickstart: validar Kanban de Pendências e Revisão de Cargos

Guia de validação ponta a ponta contra a API real (Constituição Princípios II/III).
Não duplica os contratos — ver `contracts/` para os schemas completos.

## Pré-requisitos

- API rodando localmente (`poe dev` ou equivalente) com migrações aplicadas, incluindo a
  migração de dados desta feature (`data-model.md` §3).
- Seed desta feature executado: `python -m scripts.seeds.seed_kanban` (também incluído
  em `scripts/seeds/seed_all.py`), que cria:
  - `kanban_demo_bracvam` / `KanbanDemo@123456` (perfil `bracvam`): plataforma inteira
    visível, incluindo ~300 processos distribuídos pelos 5 templates oficiais em
    estágios variados — incluindo alguns propositalmente além do `sla_hours` declarado.
  - `kanban_demo_padrao_a` / `KanbanDemo@123456` (cargo global `Padrão`): Proponente no
    "Método A" e Gestor no "Método B" — os dois processos dedicados a este cenário.
  - `kanban_demo_padrao_b` / `KanbanDemo@123456` (cargo global `Padrão`): nenhuma
    atribuição em processo algum, para provar o estado vazio.

## Cenário 1 — User Story 1 (Kanban consolidado, BraCVAM/Admin)

1. Login como o usuário `BraCVAM` semeado (`POST /auth/login`).
2. `GET /activities/kanban` (sem filtro) → confirmar `total` compatível com os ~300
   processos semeados (múltiplas atividades por processo) e `counts_by_column`
   preenchido nas quatro colunas, incluindo `EM_ATRASO` > 0.
3. `GET /activities/kanban?column=NAO_INICIADO` → conferir que atividades sem nenhuma
   `Task` (ex.: `planning_preview` de processos ainda na Fase 1) aparecem com
   `blocking_activity_key` preenchido.
4. Repetir com `column=EM_ATRASO` → conferir que só aparecem atividades cujo
   `run_started_at` + `sla_hours` já passou do prazo declarado no template.

**Resultado esperado**: todas as consultas resolvidas sem abrir nenhum processo
individualmente — confirma FR-001/FR-012/SC-001.

## Cenário 2 — User Story 2 (cargos globais x contextuais)

1. Login como o usuário `Padrão` com Proponente no Método A / Gestor no Método B.
2. `GET /auth/me` → conferir `access.scopes` com duas entradas, uma por processo, cada
   uma com o `role_key` correspondente.
3. `GET /activities/kanban` → conferir que só atividades dos Métodos A e B aparecem.
4. `GET /processes/{id do Método C}` (onde o usuário não tem atribuição) → `404`.
5. Login como o segundo usuário `Padrão` (sem nenhuma atribuição) → `GET
   /activities/kanban` → `items: []`, `total: 0` (estado vazio, não erro — FR-015).
6. Login novamente como o usuário `BraCVAM` → `GET /processes/{id do Método C}` → `200`,
   confirma acesso de plataforma independente de atribuição (FR-003).

**Resultado esperado**: confirma FR-003/FR-004/FR-005/FR-006/FR-014/SC-002/SC-004.

## Cenário 3 — User Story 3 (contexto de ordem)

1. Como o usuário `BraCVAM`, escolher no Kanban um item em `NAO_INICIADO` com
   `blocking_activity_key` preenchido.
2. Confirmar que o valor de `blocking_activity_key` corresponde a uma atividade cujo
   `status` ainda não é `COMPLETED` naquele mesmo processo (via `GET
   /processes/templates/{key}` + o estado real da instância).
3. Escolher um item em `EM_ANDAMENTO`; confirmar que `cargo` é resolvível
   (`resolve_activity_holders`) para ao menos um usuário ativo naquele processo/perfil
   global, provando que a pendência nunca fica "solta".

**Resultado esperado**: confirma FR-009/FR-010/FR-016/SC-003/SC-006.

## Cenário 4 — Demonstração (Constituição Princípio III)

1. Abrir `demos/kanban/index.html` no navegador.
2. Autenticar como o usuário `BraCVAM` semeado, diretamente pela página (chamando
   `POST /auth/login` da API real).
3. Confirmar visualmente as quatro colunas populadas e a navegação de um cartão até o
   detalhe do processo correspondente (`FR-013`).
4. Repetir com um dos usuários `Padrão`, confirmando o recorte de métodos visível.

## Portões de qualidade antes de considerar a spec concluída

- `poe format` + `poe lint` + `poe test` verdes.
- Migração de dados testada (upgrade + downgrade) em
  `tests/integration/migrations/`.
- Testes de contrato HTTP para os três endpoints modificados e o novo, cobrindo os
  casos de erro descritos em `contracts/`.
- Demo (Cenário 4) funcional contra a API real, seed reproduzível.

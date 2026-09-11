# Contrato HTTP: Correção de Visibilidade (User Story 2)

Nenhum endpoint novo nesta parte — três endpoints já existentes passam a aplicar a
mesma regra de visibilidade (`research.md` D2): o usuário só vê um processo (e suas
tarefas) se tiver acesso de plataforma (`Admin`/`BraCVAM`, D1) **ou** ao menos uma
`Assignment` ativa naquele processo, em qualquer cargo contextual.

## 1. `GET /processes` (modificado)

**Antes**: filtrava só `PROPONENT_SCOPED_STATUSES` vs. escopo do proponente; qualquer
outro status era visível a qualquer usuário autenticado.

**Depois**: adiciona, para todo status, a condição
`has_platform_wide_access(user) OR process_id IN active_participant_process_scope(user)`.
Formato de resposta inalterado (`ProcessInstanceListResponse`).

```
GET /processes?status=TRIAGE
→ 200, items: só processos onde o usuário chamador é Admin/BraCVAM
  OU tem Assignment ativa (qualquer role_key)
```

## 2. `GET /processes/{id}` (modificado)

Mesma condição adicionada ao `WHERE` existente. Usuário sem acesso → `404` (mesmo
comportamento já usado hoje para esconder existência de um recurso, consistente com o
tratamento de `PROPONENT_SCOPED_STATUSES`).

## 3. `GET /tasks` (modificado)

**Antes**: nenhum filtro de visibilidade — qualquer usuário autenticado listava todas as
tarefas de todos os processos (achado A1 do `research.md`).

**Depois**: mesmo `WHERE` de acesso de plataforma OU participação ativa, join adicional
até `ProcessInstance` (o `join` até `ActivityInstance.process_instance` já existe na
query). Parâmetros `status`, `role`, `process_id` continuam funcionando como filtros
adicionais sobre o conjunto já restrito.

## 4. `GET /auth/me` (sem alteração)

Documentado aqui só como referência: já retorna `access.profiles` (cargo global) e
`access.scopes` (lista de `{process_id, roles}` — já é "Proponente no processo A, Gestor
no processo B"). O frontend do Kanban usa este endpoint, já existente, para saber "quem
sou eu" e decorar a UI por cargo; nenhuma mudança de contrato é necessária aqui.

## Casos de erro

- Usuário `Padrão` sem nenhuma `Assignment` ativa em um processo → `404` em
  `GET /processes/{id}`, lista vazia (não erro) em `GET /processes`/`GET /tasks` quando
  filtrado por esse processo.
- Usuário `Admin`/`BraCVAM` → nunca recebe `404` por falta de participação; só por
  processo inexistente/soft-deletado (comportamento já existente, inalterado).

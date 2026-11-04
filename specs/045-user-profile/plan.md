# Implementation Plan: Perfil do Usuário

**Branch**: `feat/045-user-profile` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/045-user-profile/spec.md`

## Summary

Duas rotas de leitura entram em `routers/users.py`. `GET /users/{user_id}`
devolve o perfil: os dados da conta sem `username` e os cargos globais vigentes
com a data de atribuição. `GET /users/{user_id}/process-roles` lista os cargos
locais, paginados por processo, com o filtro `active`. Uma função do router
decide o acesso das duas rotas: a própria pessoa, ou quem tem `users.read`. A
feature reaproveita `paginate_query`, `laboratory_refs` e `ProcessRef`, sem
tabela, coluna, migração nem permissão nova.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2.

**Storage**: PostgreSQL 17, sem migração. Lê `users`, `user_access_profiles`,
`access_profiles`, `assignments`, `process_instances`, `laboratories` e
`institutions`.

**Testing**: pytest, pytest-asyncio e Testcontainers. Uma jornada por história,
a partir de `bootstrap_fresh_deploy`, em
`tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py`, e
testes focados em `tests/api/routers/test_user_profile.py`.

**Target Platform**: servidor Linux (Docker, `python:3.14-slim`)

**Project Type**: serviço web (backend)

**Performance Goals**: número fixo de consultas por requisição, qualquer que
seja o número de processos da pessoa, sem consulta por processo.

**Constraints**: contratos existentes intactos (FR-016); a resposta do perfil
nunca traz `username` nem hash de senha (FR-002); 403 antes de qualquer busca
para quem não pode consultar outra conta (FR-012).

**Scale/Scope**: duas rotas, uma função de acesso e seis schemas pequenos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado |
|---|---|
| I. Requisitos e evidência | PASS. A decisão da equipe e o pedido do frontend estão em Clarifications. A spec classifica o que é confirmado e o que é inferência, e o conflito com o Plano de Trabalho está registrado em `docs/observacoes-e-pendencias.md`. |
| II. Rastreabilidade e auditoria | PASS. A feature só lê dados. Não cria modelo nem escrita, e por isso não grava evento. |
| III. Segurança, autorização e sigilo | PASS. O backend checa o acesso a cada requisição, a partir do banco. A consulta a outra conta exige `users.read`, que hoje só Administrador e BraCVAM têm, e esses dois perfis já veem os participantes de qualquer processo. O 403 vem antes da busca e não revela se a conta existe. As respostas não trazem nome químico, CAS, SDS nem dado de execução de laboratório. |
| IV. IA como apoio | PASS. A feature não toca a IA. |
| V. Testes orientados a jornadas | PASS. Cada história tem a própria jornada pela API pública, a partir de um ambiente recém-provisionado. Erros, limites de acesso, isolamento, ordenação e paginação têm testes focados separados. |
| VI. Mudanças simples | PASS. Duas rotas no router que já cuida de `/users`, sem camada de serviço. Reaproveita os helpers de listagem e de referências. Nenhum contrato existente muda. |
| VII. Documentação do estado atual | PASS. O PR atualiza `manual/guias/administrar-usuarios-e-acessos.md` e `manual/referencia/listagens-e-referencias.md`. `manual/referencia/rotas.md` sai do OpenAPI a cada build. |

## Project Structure

### Documentation (this feature)

```text
specs/045-user-profile/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/user-profile.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/schemas.py               # schemas do perfil e dos cargos locais
src/pivma/routers/users.py         # authorize_profile_read e as duas rotas
tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py
tests/api/routers/test_user_profile.py
manual/guias/administrar-usuarios-e-acessos.md
manual/referencia/listagens-e-referencias.md
```

**Structure Decision**: as rotas ficam em `routers/users.py`, junto de
`GET /users`, porque o recurso é o mesmo. As consultas são específicas destas
duas rotas e ficam no router, como as de `list_users`. Uma função em `core/`
seria abstração de uso único.

## Design

As decisões estão justificadas em [research.md](research.md). Os campos estão em
[data-model.md](data-model.md), e as respostas e os erros em
[contracts/user-profile.md](contracts/user-profile.md).

1. **Acesso** (`authorize_profile_read(session, actor, user_id)`): retorna sem
   erro quando `actor.id == user_id` ou quando o ator tem `users.read`. Sem
   nenhum dos dois, responde 403 `forbidden` antes de consultar a conta. As
   duas rotas chamam a função antes de qualquer consulta. Quando a equipe criar
   a visão para membros comuns, ela entra nesta função (FR-015).
2. **Conta**: as duas rotas carregam `User` com
   `skip_soft_delete_filter=True`, porque a administração consulta contas
   desativadas. Sem conta, a resposta é 404 `not_found`. Esse caso só acontece
   com `users.read`, porque a própria conta sempre existe.
3. **Perfil**: uma consulta busca `AccessProfile.id`, `AccessProfile.name` e
   `UserAccessProfile.created_at`, em ordem de `created_at` e depois de
   `AccessProfile.id`. O filtro global de exclusão lógica já tira as
   atribuições e os perfis excluídos.
   `active_profiles_for_users` não serve aqui porque não devolve a data, e
   mudar o retorno dela afetaria outros chamadores.
4. **Cargos locais**:
   - Os predicados são `Assignment.user_id`, o filtro de revogação de
     `active` e o join com `ProcessInstance`. O filtro global de exclusão
     lógica já tira as designações e os processos excluídos.
   - A página sai de `paginate_query` sobre
     `select(Assignment.process_instance_id).group_by(...)`, em ordem de
     `max(assigned_at)` decrescente e depois de `process_instance_id`
     crescente. O total conta os grupos.
   - Uma segunda consulta traz as designações dos processos da página, com os
     mesmos predicados, em ordem de `assigned_at` decrescente e depois de `id`
     crescente.
   - Uma terceira traz os processos, e `laboratory_refs` traz os laboratórios.
   - O Python agrupa as designações na ordem da página.
5. **OpenAPI**: `operation_id` `getUserProfile` e `listUserProcessRoles`, com
   401, 403 e 404 descritos em `responses`, como em `GET /users`. As rotas não
   levam `x-required-permission`, porque a própria pessoa não precisa de
   permissão. A descrição de cada rota explica a regra.

## Complexity Tracking

Nenhuma violação a justificar.

Reavaliação após o desenho: sem mudanças no Constitution Check.

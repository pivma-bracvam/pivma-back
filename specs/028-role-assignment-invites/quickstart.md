# Quickstart: Validar Atribuição de Cargo por Convite com Link

**Feature**: 028-role-assignment-invites

## Pré-requisitos

- API rodando localmente (`poe dev` ou equivalente) com as migrações desta feature e da
  Issue #41 aplicadas (`alembic upgrade head`).
- `.env` com `INVITE_EXPIRATION_HOURS` definido (ou o default `1` é suficiente para o
  roteiro abaixo, exceto o passo de expiração, que precisa de um valor baixo — ex. `0`
  minutos não é válido em horas; usar um segundo processo com override, ver passo 6).
- Seed executado (a estender, conforme citado na Issue #23): processo criado
  na fase de Planejamento, com um usuário Proponente autenticável e um usuário BraCVAM.
- Cliente HTTP (ex. `/docs` do FastAPI) para as chamadas descritas abaixo.

## Passos

### 1. Designação direta fecha a etapa sozinha (US1)

1. Autenticar como o Proponente do seed.
2. `GET /processes/templates/<template-desta-etapa>` → confirmar as 8 atividades
   `activity_type: "role_assignment"` na fase de Planejamento, com `target_role_key`
   visível em cada uma.
3. `POST /processes/{id}/participants` designando um usuário ativo qualquer para
   `group_manager` (papel 2 da sequência, sem convite).
4. Repetir a consulta do roteiro do processo (Spec 017) → a etapa "Definir os
   integrantes do Grupo Gestor" aparece `COMPLETED` sem nenhuma chamada adicional de
   "concluir"; as etapas 3–8 (que dependiam de `group_manager`) mudam de `BLOCKED` para
   `IN_PROGRESS`/`READY`.

### 2. Convite por link para quem não tem conta (US2)

5. Ainda como Proponente, `POST /processes/{id}/participants/invites` com
   `{"email": "patrocinador@exemplo.org", "role_key": "sponsor"}`.
   Guardar o `token` da resposta — só aparece uma vez.
6. Em uma sessão anônima (outro navegador/aba anônima), `GET /invites/{token}` →
   confirmar `expired: false` e os dados de pré-visualização.
7. Cadastrar uma conta nova com **o mesmo e-mail** do convite (`POST /users`, Spec 001,
   endpoint inalterado).
8. Com a sessão dessa conta nova, `POST /invites/{token}/accept` → resposta traz
   `assignment_id`; conferir com `GET /processes/{id}/participants` que a nova conta
   aparece designada como `sponsor`.
9. Consultar o roteiro novamente → a etapa "Definir o Patrocinador" aparece `COMPLETED`.

### 3. E-mail divergente é recusado (FR-010)

10. Repetir o passo 5 gerando um segundo convite para outro e-mail.
11. Autenticar com uma conta cujo e-mail **não** é o do convite e chamar
    `POST /invites/{token}/accept` → esperar `403`; conferir que o convite continua
    `pending` (`GET /processes/{id}/participants/invites`).

### 4. Reenvio e revogação (US3)

12. `POST /processes/{id}/participants/invites/{invite_id}/resend` sobre o convite do
    passo 10 → novo `token` na resposta; o `token` do passo 10 deixa de funcionar em
    `GET /invites/{token_antigo}` (`404`).
13. `POST /processes/{id}/participants/invites/{invite_id}/revoke` → `GET /invites/{token}`
    (o mais recente) passa a `404`.

### 5. Múltiplos convites para o mesmo papel (FR-017)

14. Criar dois convites pendentes para `adhoc_evaluator` (papel 8, sem titularidade
    única — FR-019) com e-mails diferentes.
15. Aceitar só um deles → conferir que a etapa "Definir Especialistas Temáticos (Comitê
    ADHOC)" **continua aberta** (não `COMPLETED`) enquanto o segundo convite seguir
    `pending`.
16. Revogar o segundo convite → a etapa fecha automaticamente (FR-017: todo convite
    emitido precisa estar aceito ou revogado, mais ao menos uma designação ativa).

### 6. Expiração (FR-008)

17. Criar um convite com `INVITE_EXPIRATION_HOURS` temporariamente baixo no ambiente de
    teste (ou aguardar o prazo padrão em ambiente isolado); após o prazo,
    `GET /invites/{token}` → `expired: true`; `POST /invites/{token}/accept` → `409`.
18. Reenviar o mesmo convite (passo 12) → volta a ser aceitável com novo prazo.

## Verificação de não regressão (SC-008)

- A suíte completa (`poe test`) permanece verde, incluindo em particular
  `tests/api/routers/test_participant_router.py` (Spec 006) sem nenhuma alteração de
  comportamento para designação direta feita por quem já tinha `group_manager` ou
  permissão global — a nova matriz de autorização (FR-001/002/003) só **adiciona**
  capacidade ao Proponente, nunca remove a de quem já podia agir.
- Um processo criado a partir de uma versão de template **anterior** a esta feature
  continua sem as 8 etapas de atribuição de cargo — mesma garantia de imutabilidade de
  versão já validada pela Spec 017 (passo de não regressão do seu próprio quickstart).

## Critério de conclusão

Este quickstart só é considerado cumprido quando os 18 passos acima forem executados
manualmente contra a API real (não mocada) e a verificação de não regressão passar —
consistente com o critério de conclusão já adotado pelas specs anteriores (execução
manual contra a API real, não só suíte automatizada).

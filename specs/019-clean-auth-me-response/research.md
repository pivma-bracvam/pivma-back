# Research: Limpeza e Padronização do Contrato de Sessão Atual

Este documento registra as decisões arquiteturais, justificativas e alternativas avaliadas para a remoção da redundância no endpoint `GET /auth/me` com quebra de retrocompatibilidade intencional.

---

## Decisão 1: Modelo Pydantic de Resposta (`CurrentUserResponse`)

- **Decisão**: Alterar a definição de `CurrentUserResponse` em `src/pivma/schemas.py` para herdar diretamente de `BaseModel` (com `extra='forbid'`), contendo exclusivamente os atributos `user: UserIdentity` e `access: CurrentUserAccess`.
- **Racional**:
  - Anteriormente, `CurrentUserResponse` herdava de `UserIdentity`, o que forçava a duplicação dos campos `id`, `username`, `email` e `full_name` tanto na raiz do JSON serializado quanto dentro do nó `user`.
  - Com a remoção da herança, o payload JSON passa a ser estritamente modular e sem campos duplicados.
- **Alternativas consideradas**:
  - *Manter campos na raiz como deprecated*: Rejeitado porque o usuário solicitou expressamente a quebra de retrocompatibilidade para manter apenas a versão mais recente e limpa.
  - *Mover campos de acesso para a raiz e manter usuário plano*: Rejeitado porque misturaria conceitos cadastrais com regras de governança e RBAC, violando a separação semântica já adotada no projeto.

---

## Decisão 2: Instanciação no Router (`src/pivma/routers/auth.py`)

- **Decisão**: Remover a descompactação `**identity.model_dump()` no retorno de `read_current_user`. O endpoint passará a instanciar:
  ```python
  return CurrentUserResponse(
      user=identity,
      access=CurrentUserAccess(
          profiles=[
              ProfileSummary(id=profile.id, name=profile.name, active=True)
              for profile in profiles
          ],
          global_permissions=await effective_permission_codes(
              session, current_user.id
          ),
          scopes=scopes,
      ),
  )
  ```
- **Racional**: Elimina código dinâmico desnecessário e garante que o Pydantic valide estritamente os campos definidos no schema.
- **Alternativas consideradas**: Nenhuma relevante; a instanciação direta é o padrão idiomático FastAPI/Pydantic.

---

## Decisão 3: Atualização do Contrato OpenAPI

- **Decisão**: Atualizar o contrato formal de API (`specs/019-clean-auth-me-response/contracts/auth.openapi.yaml` e retropropagar para `specs/002-user-authentication/contracts/auth.openapi.yaml` conforme aplicável) removendo o construto `allOf: [ $ref: '#/components/schemas/UserIdentity' ]` de `CurrentUserResponse`.
- **Racional**: Garante que os esquemas OpenAPI e a documentação interativa do Swagger reflitam com precisão a assinatura estrita do endpoint.
- **Alternativas consideradas**: Nenhuma; a documentação OpenAPI deve refletir a verdade estrita do código.

---

## Decisão 4: Estratégia para Suítes de Testes

- **Decisão**:
  - Em `tests/api/routers/test_auth_router.py`:
    - Atualizar `test_login_with_username_and_recognize_identity` para esperar um dicionário contendo unicamente `{'user': {...}, 'access': {...}}`.
    - Remover asserções de primeiro nível como `assert response.json()['full_name'] == ...`, mantendo apenas a verificação sob `['user']['full_name']`.
    - Garantir que nenhum teste exija ou tolere a presença de `id`, `username`, `email` ou `full_name` na raiz da resposta de `/auth/me`.
- **Racional**: Atende à diretriz do usuário: *"testes que utilizam a estrutura anterior podem ser removidos completamente"*.
- **Alternativas consideradas**: Manter testes de tolerância a chaves legadas (rejeitado por contrariar o objetivo de limpeza).

---

## Decisão 5: Migração de Consumidores das Páginas de Demonstração (`demos/`)

- **Decisão**: Atualizar todas as páginas de demonstração que utilizam `GET /auth/me` para ler atributos a partir do nó `user` (ex.: `data.user.full_name || data.user.username` em vez de `data.full_name || data.username`).
  - Módulos impactados: `demos/ai-pipeline/app.js`, `demos/attachments/index.html`, `demos/forms/ai-config.html`, `demos/forms/index.html`, `demos/operational-index/app.js`, `demos/roadmap/index.html`, `demos/submission/index.html`, `demos/triage/index.html`, `demos/users/index.html`.
  - Nota: `demos/kanban/index.html` já consome `user.user.*` e não requer alteração de compatibilidade.
- **Racional**: Em conformidade com o Princípio III da Constituição e com `AGENTS.md`, as demonstrações devem permanecer 100% funcionais interagindo com a API real.
- **Alternativas consideradas**: Deixar as demos inalteradas com polyfill no frontend (rejeitado: o frontend de demonstração deve consumir a API limpa diretamente).

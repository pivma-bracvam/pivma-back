# Research: Autogestão de Nome e Senha da Própria Conta

Não restaram itens `NEEDS CLARIFICATION` no contexto técnico. As decisões abaixo registram as escolhas de desenho e o que foi verificado no código da `origin/develop` (commit `8560237`).

## 1. Onde a rota fica

- **Decision**: adicionar `PATCH /auth/me` em `src/pivma/routers/auth.py`, ao lado de `GET /auth/me`.
- **Rationale**: a issue #43 define essa rota. O router `auth` já agrupa as operações sobre a própria sessão e importa `CurrentUser`, `Session`, `TrustedOrigin` e `verify_password`.
- **Alternatives considered**: reaproveitar `PATCH /users/{user_id}` liberando o próprio `user_id` foi descartado: misturaria autorização administrativa e de autogestão na mesma rota e exigiria exceções em `users.manage`.

## 2. Schema de entrada

- **Decision**: criar `SelfUserUpdate` em `src/pivma/schemas.py` com `extra='forbid'`, `full_name: FullNameValue = None`, `new_password` com as mesmas restrições de `UserSchema.password` (8 a 128 caracteres, validador sem espaços) e `current_password` com 1 a 128 caracteres. Um `model_validator(mode='after')` aplica as combinações de FR-005 e FR-008.
- **Rationale**: reaproveita `FullNameValue` e a política de senha já existentes, sem nova abstração. `extra='forbid'` atende FR-004. Campos tipados como `str` rejeitam `null` na própria validação de tipo, como já ocorre em `UserUpdate`.
- **Por que `current_password` aceita de 1 a 128 caracteres**: a senha atual não é uma senha nova e não deve passar pela política de cadastro. Com mínimo 8, uma senha atual errada e curta voltaria 422 em vez do 400 exigido por US2-2. O teto de 128 limita o custo do Argon2 sobre entradas enormes, e nenhuma senha cadastrada passa desse limite.
- **Alternatives considered**: extrair um tipo `PasswordValue` compartilhado entre `UserSchema`, `UserUpdate` e o novo schema foi descartado nesta entrega. Seria uma refatoração de código que funciona, fora do escopo (Constituição V). O validador de espaços é repetido no novo schema, seguindo o padrão atual do arquivo.

## 3. Regras de combinação do corpo

- **Decision**: o `model_validator` rejeita com `ValueError` (vira 422 pelo formatador da Spec 034), conferindo nesta ordem:
  1. `current_password` sem `new_password` → "Informe a nova senha.";
  2. `new_password` sem `current_password` → "Informe a senha atual para trocar a senha.";
  3. corpo sem `full_name` e sem `new_password` → "Informe o nome completo ou a nova senha.".
- **Por que essa ordem**: o corpo `{"current_password": ...}` também se encaixa na regra 3. Conferindo a regra 1 antes, a mensagem aponta o que falta de fato (a nova senha).
- **Rationale**: cobre FR-005, FR-008 e o edge case da senha atual enviada sozinha ou com o nome. Rejeitar `current_password` sem `new_password` evita um campo ignorado em silêncio.
- **Alternatives considered**: ignorar `current_password` quando só o nome muda foi descartado, porque esconderia erro do cliente.

## 4. Senha atual incorreta

- **Decision**: verificar `current_password` com `verify_password` em `run_in_threadpool` **antes** de qualquer atribuição na entidade. Se falhar, `api_error(HTTPStatus.BAD_REQUEST, 'invalid_current_password', 'Senha atual incorreta.')`.
- **Rationale**: 400 conforme a spec (401 significa sessão inválida). Verificar antes de alterar a entidade garante a atomicidade de FR-011 sem `rollback` explícito. O threadpool segue o padrão de `login` e `prepare_user_changes`, porque o Argon2 é bloqueante.
- **Alternatives considered**: atribuir e depois desfazer com `rollback` foi descartado por ser mais frágil. Aplicar o hash fictício (`DUMMY_PASSWORD_HASH`) é desnecessário: a conta já está identificada pela sessão, então não há enumeração de usuários a proteger.

## 5. Persistência, auditoria e erros inesperados

- **Decision**: alterar diretamente o `current_user` vindo de `CurrentUser`, gerar o hash com `hash_password` em `run_in_threadpool`, chamar `current_user.set_update_audit(current_user.id)`, depois `await session.commit()` e `await session.refresh(current_user)`.
- **Rationale**: o FastAPI resolve `get_session` uma vez por requisição, então `get_current_user` e a rota usam a mesma `AsyncSession` e o objeto já está nela. `set_update_audit` é o padrão de auditoria existente (Constituição II).
- **Sem `try/except` para `IntegrityError`**: a rota não altera colunas únicas (`username`, `email`), então esse conflito não pode ocorrer. Uma falha inesperada no commit já vira 500 `internal_error` pelo handler global de `src/pivma/errors.py`, e a `AsyncSession` desfaz a transação ao ser fechada. Repetir o bloco de `users.py` seria código para cenário impossível.

## 6. Resposta

- **Decision**: `response_model=UserPublic` e `operation_id='updateCurrentUser'`, com `responses` documentando 400, 401 e 403, como em `PATCH /users/{user_id}`.
- **Rationale**: atende FR-013 e o requisito de não criar um formato novo. `UserPublic` não tem campo de senha nem de hash (SC-006).

## 7. Lacuna encontrada: mascaramento dos novos campos de senha

- **Achado (CONFIRMADO)**: `src/pivma/core/errors.py` (`_field_error`) só esconde a regra e a mensagem da senha quando algum segmento do caminho é **exatamente** `'password'`. Para `current_password` e `new_password`, um 422 devolveria a regra (por exemplo, "Deve ter pelo menos 8 caracteres."), contrariando a decisão da Spec 034 (FR-010).
- **Decision**: trocar a condição para reconhecer qualquer segmento que termine em `password` (`any(str(part).endswith('password') for part in path)`) e cobrir com um teste unitário em `tests/unit/core/test_errors.py`.
- **Rationale**: a mudança tem uma linha, mantém o comportamento atual para `password` e fecha a lacuna para os campos novos, sem criar lista de nomes para manter. Hoje nenhum outro campo da API termina em `password`.
- **Alternatives considered**: nomear os campos como `password` aninhado (ex.: `{"password": {"current", "new"}}`) foi descartado porque contraria o contrato da issue #43.

## 8. Itens deliberadamente fora (sem débito novo)

- Revogação de sessões após a troca de senha e limite de tentativas: dependem de infraestrutura que não existe, e a spec os registra em Assumptions e Out of Scope.
- Nenhuma migração, dependência, tabela ou camada de serviço nova.
- `docs/observacoes-e-pendencias.md`, citado pela constituição, foi removido de propósito no commit `9caba12` ("docs: remover documentacao e planejamento legados"). Recriá-lo contrariaria essa decisão da equipe. Por isso as decisões e os itens fora do escopo ficam registrados na spec (Assumptions e Out of Scope), e nenhuma lacuna fica pendente de validação para esta implementação. Atualizar a referência na constituição exige emenda própria (Governance) e fica fora desta entrega.

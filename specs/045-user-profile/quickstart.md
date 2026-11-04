# Quickstart: Perfil do Usuário

## Testes

```bash
poetry run pytest tests/api/routers/test_user_profile.py tests/integration/journeys/etapa_1_submissao_triagem/test_user_profile.py
```

Depois rode a suíte completa, o lint e o build do manual:

```bash
poe lint && poe test && poe docs-build
```

`poe test` deve passar sem mudar as asserções existentes (SC-006).

## Validação manual

Com a API em `http://localhost:8000` e o banco provisionado pelo bootstrap:

1. Cadastre uma conta comum, entre com ela e guarde o `user.id` de
   `GET /auth/me`.
2. Crie dois processos com `POST /processes`. Em cada um, a conta passa a ter o
   cargo `proponent`.
3. `GET /users/{id}`: a resposta traz nome, e-mail, `active`, `created_at` e
   `global_profiles`, sem `username` ([contrato](contracts/user-profile.md)).
4. `GET /users/{id}/process-roles`: dois itens, o processo mais recente primeiro,
   cada um com o cargo `proponent`.
5. Com a mesma conta, `GET /users/{id-do-admin}` deve responder 403. Repita com
   um UUID aleatório: a resposta deve ser a mesma.
6. Entre como Administrador:
   - `GET /users/{id}` e `GET /users/{id}/process-roles` devolvem o mesmo que a
     própria conta recebeu.
   - Um UUID aleatório responde 404.
7. Como Administrador, designe e revogue um cargo da conta pelas rotas de
   participantes. Depois, `GET /users/{id}/process-roles?active=false` traz o
   cargo com `revoked_at` preenchido, e a consulta sem filtro não o traz.

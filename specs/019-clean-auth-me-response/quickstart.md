# Quickstart: Limpeza e Padronização do Contrato de Sessão Atual

Este guia fornece instruções para validar localmente a reestruturação e a quebra de retrocompatibilidade do endpoint `GET /auth/me`.

---

## Pré-requisitos

1. Ambiente virtual ativo (`poetry` ou `uv`).
2. Dependências instaladas e contêineres de desenvolvimento disponíveis.

---

## 1. Validação Manual via API

### Passo 1: Autenticação
Execute uma requisição de login para gerar o cookie de sessão:
```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "admin", "password": "Password123!"}' \
  -c cookies.txt
```

### Passo 2: Consulta à Sessão Atual
Consulte o endpoint `GET /auth/me` utilizando os cookies salvos:
```bash
curl -s -X GET http://localhost:8000/auth/me \
  -b cookies.txt | jq .
```

### Resultado Esperado
O JSON retornado DEVE conter exclusivamente as chaves de primeiro nível `"user"` e `"access"`:
```json
{
  "user": {
    "id": "b260299c-0424-474e-9baf-697ef4a3bd8c",
    "username": "admin",
    "email": "admin@bracvam.fiocruz.br",
    "full_name": "Administrador do Sistema BraCVAM"
  },
  "access": {
    "profiles": [ ... ],
    "global_permissions": [ ... ],
    "scopes": [ ... ]
  }
}
```

**Verificação de quebra de compatibilidade**:
```bash
# Deve retornar 'null'
curl -s -X GET http://localhost:8000/auth/me -b cookies.txt | jq '.id, .username, .email, .full_name'
```

---

## 2. Validação Automatizada (Testes)

Execute a suíte focada no roteador de autenticação para comprovar conformidade de contrato:
```bash
pytest tests/api/routers/test_auth_router.py
```

Execute a suíte geral de integração de routers para validar não regressão:
```bash
pytest tests/api/routers/
```

---

## 3. Validação das Telas de Demonstração (`demos/`)

1. Inicie a aplicação:
   ```bash
   poe dev  # ou uvicorn pivma.main:app --reload
   ```
2. Abra no navegador qualquer uma das demonstrações migradas (ex.: `http://localhost:8000/demos/users/` ou `http://localhost:8000/demos/kanban/`).
3. Realize login com a conta de teste.
4. Verifique que o nome do usuário e suas credenciais continuam sendo renderizados com sucesso no painel de identificação superior.

# Guia de Autenticação e Sessão para o Frontend

Este guia orienta os desenvolvedores de frontend sobre como gerenciar autenticação, tokens JWT e sessões com o backend da PIVMA.

---

## 🔐 Fluxo de Login

O backend suporta autenticação via JSON no endpoint de login:

```http
POST /auth/login
Content-Type: application/json

{
  "username": "proponent_user",
  "password": "Password123!"
}
```

### Resposta de Sucesso (`200 OK`)
O backend retorna o cookie HttpOnly e também o token no payload JSON:

```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "c1a93b47-68b2-48a1-9c3f-7e9b41a93b01",
    "username": "proponent_user",
    "email": "proponente@lab.fiocruz.br",
    "full_name": "Dr. Carlos Proponente",
    "roles": ["proponent"]
  }
}
```

---

## 🍪 Envio de Credenciais em Requisições

Em requisições subsequentes a partir do frontend (React, Vue, Fetch API, Axios), envie sempre as credenciais incluídas para suportar tanto cookies de sessão quanto o header `Authorization`:

### Exemplo com Fetch API:
```javascript
const response = await fetch('/processes', {
  method: 'GET',
  credentials: 'include', // Envia cookies HttpOnly automaticamente
  headers: {
    'Accept': 'application/json',
    'Authorization': `Bearer ${accessToken}` // Opcional se os cookies estiverem ativos
  }
});

if (response.status === 401) {
  // Sessão expirada -> Redirecionar para tela de login
  window.location.href = '/login';
}
```

---

## 🚪 Logout Seguro

Para encerrar a sessão e invalidar cookies no navegador:

```http
POST /auth/logout
```
O backend limpa os cookies de autenticação e revoga a sessão.

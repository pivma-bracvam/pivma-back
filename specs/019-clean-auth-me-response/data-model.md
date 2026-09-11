# Data Model: Limpeza e Padronização do Contrato de Sessão Atual

Este documento descreve os schemas e modelos de transferência de dados (DTOs) que compõem a resposta do endpoint de identidade da sessão (`GET /auth/me`), formalizando a separação entre os dados cadastrais do usuário e os privilégios de acesso.

---

## 1. Schemas de Dados (Pydantic DTOs)

### `UserIdentity`
Representa os atributos cadastrais essenciais do usuário autenticado.

- **Campos**:
  - `id` (`UUID`): Identificador único do usuário.
  - `username` (`str`): Nome de usuário do operador.
  - `email` (`str`): E-mail institucional do operador.
  - `full_name` (`str | None`): Nome completo do usuário (anulável para contas legadas).
- **Configuração**: `extra = 'ignore'` (ou herdado de `UserPublic`).

---

### `ProfileSummary`
Resumo dos perfis globais associados ao usuário.

- **Campos**:
  - `id` (`UUID`): Identificador do perfil.
  - `name` (`str`): Nome legível do perfil (ex.: "Administrador").
  - `active` (`bool`): Indicador de ativação do perfil (sempre `True` no contexto de sessão ativa).
- **Configuração**: `extra = 'forbid'`.

---

### `AccessScope`
Escopo de participação e papéis atribuídos ao usuário no contexto de processos ou laboratórios específicos.

- **Campos**:
  - `process_id` (`UUID`): Identificador da instância do processo.
  - `institution_id` (`UUID | None`): Identificador da instituição associada, se aplicável.
  - `laboratory_id` (`UUID | None`): Identificador do laboratório participante, se aplicável.
  - `roles` (`list[str]`): Lista de papéis exercidos pelo usuário no escopo delimitado (ex.: `["proponent"]`, `["group_manager"]`).
- **Configuração**: `extra = 'forbid'`.

---

### `CurrentUserAccess`
Encapsula todos os dados de governança, autorização e RBAC da sessão ativa.

- **Campos**:
  - `profiles` (`list[ProfileSummary]`): Lista dos perfis globais atribuídos e ativos.
  - `global_permissions` (`list[str]`): Lista de códigos textuais das permissões globais efetivas calculadas para o usuário.
  - `scopes` (`list[AccessScope]`): Lista de escopos contextuais ativos por processo/laboratório.
- **Configuração**: `extra = 'forbid'`.

---

### `CurrentUserResponse` (Modelo Refatorado)
Contrato principal retornado por `GET /auth/me`. Não herda mais de `UserIdentity`.

- **Campos**:
  - `user` (`UserIdentity`): Objeto contendo os dados de identidade do operador.
  - `access` (`CurrentUserAccess`): Objeto contendo o contexto de acesso e autorização.
- **Configuração**: `ConfigDict(extra='forbid')`.

---

## 2. Diagrama Estrutural do Payload JSON

```text
CurrentUserResponse
├── user: UserIdentity
│   ├── id: UUID
│   ├── username: string
│   ├── email: string
│   └── full_name: string | null
└── access: CurrentUserAccess
    ├── profiles: list[ProfileSummary]
    │   └── [ { id, name, active } ]
    ├── global_permissions: list[string]
    │   └── [ "users.read", "rbac.read", ... ]
    └── scopes: list[AccessScope]
        └── [ { process_id, institution_id, laboratory_id, roles } ]
```

---

## 3. Comparativo de Mudança no Payload

### Antes (Redundante com campos na raiz):
```json
{
  "id": "b260299c-0424-474e-9baf-697ef4a3bd8c",
  "username": "admin",
  "email": "admin@bracvam.fiocruz.br",
  "full_name": "Administrador do Sistema BraCVAM",
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

### Depois (Estruturado e Limpo):
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

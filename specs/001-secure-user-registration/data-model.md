# Data Model: Cadastro Seguro de Usuários

## Usuário

Representa a conta criada pelo cadastro. Esta feature não adiciona perfil, vínculo institucional,
sessão ou estado de autenticação.

| Campo | Tipo lógico | Obrigatório | Regra |
|---|---|---:|---|
| `id` | UUID | sim | Gerado pelo sistema; chave primária |
| `username` | texto | sim | Após trim externo, 3–64 caracteres; `[A-Za-z0-9._-]`; caixa preservada |
| `email` | e-mail | sim | Após trim externo, formato válido; caixa preservada |
| `password_hash` | texto | sim | Valor Argon2id codificado; nunca exposto |
| `created_at` | data e hora | sim | Gerado pelo banco na criação |
| `created_by` | UUID opcional | não | `null` no cadastro público sem usuário autenticado |
| `updated_at` | data e hora opcional | não | Mantido pelo `AuditMixin` |
| `updated_by` | UUID opcional | não | Mantido pelo `AuditMixin` |
| `deleted_at` | data e hora opcional | não | Define exclusão lógica |
| `deleted_by` | UUID opcional | não | Mantido pelo `AuditMixin` |

### Invariantes

- Entre usuários ativos (`deleted_at IS NULL`), `lower(username)` é único.
- Entre usuários ativos (`deleted_at IS NULL`), `lower(email)` é único.
- A unicidade ignora caixa, mas o valor persistido e devolvido preserva a caixa após trim externo.
- A exclusão lógica libera username e e-mail para um novo cadastro (comportamento revertido em
  2026-08-12; ver `plan.md`).
- `password_hash` contém somente representação Argon2id codificada.
- A senha original e o hash Argon2id não aparecem no contrato público.
- Imediatamente após o cadastro público, `created_at` está preenchido e `created_by`, `updated_at`,
  `updated_by`, `deleted_at` e `deleted_by` estão nulos.

### Transições

Esta feature cobre apenas:

1. **Pedido recebido**: dados ainda não persistidos.
2. **Rejeitado**: validação ou conflito falhou; nenhum usuário é criado.
3. **Criado**: usuário persistido uma vez, com hash e auditoria de criação.

Falha inesperada de hashing, `flush` ou `commit` executa rollback e retorna HTTP 500 genérico; não
constitui uma transição persistida.

Não há ativação, autenticação, alteração ou recuperação de senha neste escopo.

> **Nota (2026-08-12)**: esta versão não inclui bloqueio de senha por lista local. A seção
> "Lista de senhas bloqueadas" que existia aqui foi removida; ver Session 2026-08-12 em `spec.md`
> para o registro da decisão e o item de backlog correspondente.

## Migração

1. Detectar duplicidades por `lower(username)` e `lower(email)` entre usuários ativos
   (`deleted_at IS NULL`).
2. Abortar antes de qualquer mutação se houver colisão; não escolher vencedor nem expor credenciais.
3. Renomear `password` para `password_hash` somente após o preflight passar.
4. Remover o índice anterior de e-mail.
5. Criar índices únicos parciais case-insensitive para username e e-mail, restritos a
   `deleted_at IS NULL`.

A migração não inspeciona o formato da credencial armazenada, não converte, reprotege nem invalida
credenciais existentes, e não altera a caixa dos identificadores.

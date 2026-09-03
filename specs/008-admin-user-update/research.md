# Research: Atualização Administrativa de Usuários

## 1. Operação administrativa

- **Decision**: implementar `PATCH /users/{user_id}` com escopo inicial em `full_name`.
- **Rationale**: o backlog técnico confirma a necessidade de operações administrativas de atualização e deixa a definição de rotas e contratos para a spec da feature. O identificador no caminho evita ambiguidade e segue as rotas específicas já existentes no backend.
- **Alternatives considered**: `PATCH /users` foi descartado porque representaria atualização em lote; edição pelo próprio usuário foi deixada para outra feature.

## 2. Autorização

- **Decision**: criar a capacidade `users.manage`, separada de `users.read`, e semeá-la no perfil oficial Administrador.
- **Rationale**: a consulta não deve conceder capacidade de mutação. O projeto já usa permissões nomeadas por ação e dependências FastAPI para validar autorização no backend.
- **Alternatives considered**: reutilizar `users.read` foi descartado por misturar leitura e alteração; reutilizar permissões de RBAC não representa a operação de conta.

## 3. Compatibilidade de contas legadas

- **Decision**: exigir `full_name` em novos cadastros, manter a coluna anulável e permitir que o PATCH preencha contas antigas ou mockadas.
- **Rationale**: a equipe não quer migração obrigatória de dados mockados, mas quer garantir o dado em novos registros.
- **Alternatives considered**: preencher nomes automaticamente foi descartado porque inventaria dados; tornar a coluna `NOT NULL` foi descartado porque quebraria registros legados.

## 4. Auditoria

- **Decision**: atualizar `updated_at` e `updated_by` por meio do `AuditMixin` existente.
- **Rationale**: `User` já possui os campos de auditoria e não existe uma trilha genérica de alterações de conta. A feature não deve criar uma tabela de eventos sem requisito específico.
- **Alternatives considered**: usar `RbacChange` foi descartado porque a alteração não é uma mudança de RBAC; criar uma nova trilha foi deixado para uma feature de auditoria caso o domínio exija histórico detalhado.

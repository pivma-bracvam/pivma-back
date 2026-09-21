# Research: Desativação de Conta de Usuário

## 1. Desativação e auditoria

- **Decision**: Chamar `User.set_deletion_audit(actor.id)` para desativar a conta.
- **Rationale**: `AuditMixin` já define `deleted_at`, `deleted_by` e o método que usa `func.now()`. A tabela `users` já possui índices parciais para contas ativas.
- **Alternatives considered**: Exclusão física, novos campos e um evento de auditoria dedicado foram descartados por FR-003 e FR-013.

## 2. Acesso à conta inativa

- **Decision**: Manter a revogação baseada na consulta ativa existente, sem estado de sessão adicional.
- **Rationale**: `get_current_user` e o login consultam `User.deleted_at IS NULL`; um token emitido antes da desativação e uma nova tentativa de login recebem 401 quando a conta fica inativa.
- **Alternatives considered**: Blacklist de JWT, versão de token e limpeza de cookie foram descartadas porque não são necessárias para o contrato e ampliariam o escopo.

## 3. Proteção da última conta administrativa

- **Decision**: Depois de marcar a conta para exclusão lógica e executar `flush`, chamar `ensure_administrator_remains` antes do `commit`.
- **Rationale**: A função bloqueia o perfil de sistema `administrator` e verifica uma conta ativa com todas as permissões administrativas. O router RBAC já usa essa ordem para alterações concorrentes de perfis e designações.
- **Alternatives considered**: Contar administradores fora da transação, criar um lock próprio ou uma restrição no banco foram descartados. A função existente centraliza a invariante e serializa as alterações relevantes.

## 4. Conta alvo e visibilidade de inativas

- **Decision**: Buscar a conta alvo com `SELECT ... FOR UPDATE`, sem ignorar o filtro global de soft-delete.
- **Rationale**: O filtro global restringe a busca a contas ativas. O bloqueio impede duas desativações simultâneas da mesma conta; `GET /users?active=false` já usa o opt-out correto para listar inativas.
- **Alternatives considered**: `session.get`, atualização em massa e `skip_soft_delete_filter=True` foram descartados. Eles não atendem simultaneamente à serialização, à resposta 404 para conta inativa e ao fluxo de auditoria.

## 5. Respostas de conflito e recurso ausente

- **Decision**: Responder 409 para autodesativação e para a última conta administrativa; responder 404 para UUID inexistente ou conta já inativa.
- **Rationale**: A issue permite 400 ou 409 para autodesativação, e a spec registra 409 como PROPOSTA. O filtro ativo atual trata conta inativa como não encontrada para a operação.
- **Alternatives considered**: 400 para autodesativação e 409 para conta inativa foram descartados para manter um único contrato de conflito e não expor uma operação repetida como estado mutável.

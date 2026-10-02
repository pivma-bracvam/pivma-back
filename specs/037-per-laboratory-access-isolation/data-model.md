# Data Model: Isolamento de acesso por laboratório

Nenhuma entidade, coluna, índice ou migração nova.

## Entidades usadas

- **ActivityRun.laboratory_id** (Spec 036): laboratório da execução; nulo na
  execução de processo inteiro.
- **Assignment** (`role_key`, `laboratory_id`, `revoked_at`, `deleted_at`):
  designação. Efetiva quando ativa e, para cargo laboratorial, com vínculo
  institucional ativo (Spec 035).
- **Índice `uq_assignments_active`** (processo, usuário, cargo; onde
  `revoked_at` e `deleted_at` são nulos): impede duas designações ativas do
  mesmo cargo para o mesmo usuário no processo (FR-008).

## Regra de acesso à execução de laboratório

Ver [contracts/access-matrix.md](contracts/access-matrix.md) e
[research.md R2](research.md).

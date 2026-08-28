# Data Model: Vinculação Institucional

## Visão geral

```text
User 1 ── * UserInstitutionalAffiliation * ── 1 Institution
                         │
                         └── 0..1 Laboratory * ── 1 Institution

InstitutionalChange ── referência lógica ── Institution | Laboratory | Affiliation
```

O vínculo registra sempre uma instituição. O laboratório é opcional e, quando informado, precisa pertencer à mesma instituição. Não existe vínculo principal ou contexto selecionado; a união dos vínculos efetivamente ativos forma o escopo do usuário.

## Campos comuns de auditoria

As quatro entidades novas usam o `AuditMixin` existente.

| Campo | Tipo | Nulável | Uso |
|---|---|---:|---|
| `created_at` | timestamp | não | Momento da criação |
| `updated_at` | timestamp | sim | Momento da última alteração |
| `deleted_at` | timestamp | sim | Momento da inativação lógica |
| `created_by` | UUID, FK para `users.id` | sim no banco | Responsável pela criação |
| `updated_by` | UUID, FK para `users.id` | sim | Responsável pela última alteração |
| `deleted_by` | UUID, FK para `users.id` | sim | Responsável pela inativação |

As operações da API autenticada sempre informam o responsável. A nulabilidade preserva o padrão atual para dados de sistema e migrações.

## Institution

Tabela: `institutions`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK, gerado pela aplicação |
| `name` | varchar(255) | obrigatório; valor normalizado pelo schema |
| auditoria | `AuditMixin` | estado ativo quando `deleted_at IS NULL` |

Índices e constraints:

- Índice único parcial por `lower(name)` enquanto `deleted_at IS NULL`.
- Índice de listagem por `lower(name), id`.
- FKs de auditoria sem exclusão em cascata.

**DECISÃO TÉCNICA REGISTRADA:** instituições ativas não repetem nome sem diferenciar maiúsculas e minúsculas. Um nome pode voltar a ser usado após a inativação do ciclo anterior.

## Laboratory

Tabela: `laboratories`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK, gerado pela aplicação |
| `institution_id` | UUID | FK obrigatória para `institutions.id` |
| `name` | varchar(255) | obrigatório; valor normalizado pelo schema |
| auditoria | `AuditMixin` | estado ativo quando `deleted_at IS NULL` |

Índices e constraints:

- Constraint única em `(id, institution_id)` para ser alvo da FK composta do vínculo.
- Índice único parcial por `institution_id, lower(name)` enquanto `deleted_at IS NULL`.
- Índice de listagem por `institution_id, lower(name), id`.
- A FK não usa exclusão em cascata.

**DECISÃO TÉCNICA REGISTRADA:** laboratórios ativos não repetem nome dentro da mesma instituição sem diferenciar maiúsculas e minúsculas. A instituição do laboratório é imutável; corrigir a instituição exige inativar o registro incorreto e criar outro ciclo.

## UserInstitutionalAffiliation

Tabela: `user_institutional_affiliations`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK, gerado pela aplicação |
| `user_id` | UUID | FK obrigatória para `users.id` |
| `institution_id` | UUID | FK obrigatória para `institutions.id` |
| `laboratory_id` | UUID | opcional |
| auditoria | `AuditMixin` | ciclo ativo quando `deleted_at IS NULL` |

Índices e constraints:

- FK simples de `user_id` para `users.id`.
- FK simples de `institution_id` para `institutions.id`.
- FK composta `(laboratory_id, institution_id)` para `laboratories(id, institution_id)`. Quando `laboratory_id` for nulo, a regra composta não se aplica.
- Índice único parcial em `(user_id, institution_id)` quando o vínculo está ativo e `laboratory_id IS NULL`.
- Índice único parcial em `(user_id, institution_id, laboratory_id)` quando o vínculo está ativo e `laboratory_id IS NOT NULL`.
- Índice para consulta de escopo em `(user_id, institution_id, laboratory_id)` quando `deleted_at IS NULL`.
- FKs sem exclusão em cascata.

Validações transacionais antes da inserção:

- usuário, instituição e laboratório opcional precisam estar ativos;
- o laboratório precisa pertencer à instituição enviada;
- a combinação ativa não pode existir.

As constraints do banco são a garantia final para concorrência e gravações fora do fluxo comum.

## InstitutionalChange

Tabela: `institutional_changes`

| Campo | Tipo | Regras |
|---|---|---|
| `id` | UUID | PK, gerado pela aplicação |
| `action` | varchar(64) | ação concluída |
| `target_type` | varchar(32) | `institution`, `laboratory` ou `affiliation` |
| `target_id` | UUID | identificador lógico do alvo |
| auditoria | `AuditMixin` | `created_by` é o ator e `created_at` é a ocorrência |

Índices e constraints:

- Índice `(created_at DESC, id DESC)` para paginação e ordenação determinística.
- `target_id` não possui FK porque referencia três tabelas e precisa sobreviver aos respectivos ciclos históricos.

Ações previstas:

- `institution.created`, `institution.updated`, `institution.deactivated`;
- `laboratory.created`, `laboratory.updated`, `laboratory.deactivated`;
- `affiliation.created`, `affiliation.deactivated`.

Tentativas negadas ou inválidas não geram uma mudança concluída. O evento e a alteração do alvo pertencem à mesma transação.

## Seed do RBAC

A migração amplia as tabelas de RBAC existentes, sem criar outro modelo de autorização.

| UUID | Código | Perfil inicial |
|---|---|---|
| `00000000-0000-0000-0000-000000000104` | `institutional.read` | Administrador |
| `00000000-0000-0000-0000-000000000105` | `institutional.catalogs.manage` | Administrador |
| `00000000-0000-0000-0000-000000000106` | `institutional.affiliations.manage` | Administrador |

As três composições iniciais usam UUIDs terminados em `204`, `205` e `206`. Nenhum outro perfil recebe essas permissões na migração. O downgrade remove qualquer composição que passe a referenciar os três códigos antes de remover as permissões, preservando os demais perfis, permissões e atribuições.

## Estado efetivo

O estado persistido de cada entidade é derivado de `deleted_at`:

| `deleted_at` | Estado persistido |
|---|---|
| `NULL` | ativo |
| preenchido | inativo |

Um vínculo compõe o escopo somente quando todas as condições são verdadeiras:

```text
affiliation.deleted_at IS NULL
AND user.deleted_at IS NULL
AND institution.deleted_at IS NULL
AND (
  affiliation.laboratory_id IS NULL
  OR laboratory.deleted_at IS NULL
)
```

A inativação da instituição ou do laboratório não altera os vínculos em massa. Ela apenas os torna ineficazes para o escopo atual. A consulta administrativa por usuário continua mostrando todos os ciclos, com `active` calculado pelo estado conjunto.

## Transições permitidas

### Instituição e laboratório

| Origem | Operação | Destino | Auditoria |
|---|---|---|---|
| inexistente | criar | ativo | criação + mudança institucional |
| ativo | alterar nome | ativo | atualização + mudança institucional |
| ativo | inativar | inativo | exclusão lógica + mudança institucional |

### Vínculo

| Origem | Operação | Destino | Auditoria |
|---|---|---|---|
| inexistente | criar | ativo | criação + mudança institucional |
| ativo | inativar | inativo | exclusão lógica + mudança institucional |
| inativo | criar combinação equivalente | novo ciclo ativo | novo identificador e nova criação |

Não há transição de inativo para ativo, alteração direta de vínculo ou exclusão física. A correção encerra o vínculo incorreto e cria outro.

## Schemas públicos

- `InstitutionCreate`: `name`.
- `InstitutionUpdate`: `name`, obrigatório por ser o único campo alterável.
- `InstitutionPublic`: identificador, nome, `active` e auditoria.
- `LaboratoryCreate`: `institution_id`, `name`.
- `LaboratoryUpdate`: `name`, obrigatório; não move o laboratório.
- `LaboratoryPublic`: identificador, instituição, nome, `active` e auditoria.
- `AffiliationCreate`: `institution_id`, `laboratory_id` opcional.
- `AffiliationPublic`: identificadores e resumos de instituição e laboratório, `active` efetivo e auditoria.
- `SelfAffiliationPublic`: identificador e resumos do próprio vínculo efetivamente ativo, sem expor os identificadores de atores da administração.
- `InstitutionalChangePublic`: identificador, ação, tipo e identificador do alvo, ator e momento.
- `InstitutionalChangePage`: `offset`, `limit` e itens.

Entradas rejeitam campos extras. Nomes removem espaços nas extremidades, exigem ao menos um caractere e aceitam no máximo 255 caracteres.

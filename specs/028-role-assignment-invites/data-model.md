# Data Model: Atribuição de Cargo por Convite com Link Compartilhável

**Feature**: 028-role-assignment-invites
**Spec**: [spec.md](spec.md) · **Pesquisa**: [research.md](research.md)

Uma tabela nova (migração DDL pura) e uma extensão declarativa do YAML de template
(sem migração) — nada mais. Nenhuma coluna nova em `assignments`, `activity_instances`
ou `tasks`.

## 1. Tabela nova: `role_assignment_invites`

```text
role_assignment_invites
├── id                    UUID PK
├── process_instance_id   UUID FK → process_instances.id
├── role_key              VARCHAR(64)         -- mesmo vocabulário de ParticipantRole
├── laboratory_id         UUID FK → laboratories.id, NULL
│                         -- obrigatório quando role_key ∈ LABORATORY_ROLE_KEYS, proibido caso contrário
│                         -- mesma regra de validate_laboratory_requirement (ParticipantAssignmentCreate)
├── email                 VARCHAR(320) NOT NULL   -- RFC 5321 max; sempre presente (FR-004)
├── channel               VARCHAR(32) NOT NULL DEFAULT 'link'
│                         -- único valor válido nesta entrega; sem CHECK de banco para não
│                         -- travar a adição de 'email'/'whatsapp'/'telegram' sem migração (FR-007)
├── token_hash             VARCHAR(64) NOT NULL UNIQUE  -- sha256 hexdigest do token bruto (R1)
├── status                 VARCHAR(16) NOT NULL DEFAULT 'pending'  -- 'pending' | 'accepted' | 'revoked'
│                         -- expirado é estado DERIVADO (expires_at < now() AND status='pending'),
│                         -- nunca gravado — mesmo padrão de "Em Atraso" no Kanban (Spec 018, D3)
├── expires_at             TIMESTAMPTZ NOT NULL
├── accepted_at             TIMESTAMPTZ NULL
├── accepted_by             UUID FK → users.id, NULL
├── revoked_at               TIMESTAMPTZ NULL
├── revoked_by               UUID FK → users.id, NULL
├── created_at / created_by  (AuditMixin)
├── updated_at / updated_by  (AuditMixin — todo reenvio grava aqui, R2)
└── deleted_at / deleted_by  (AuditMixin — não usado por esta feature; soft-delete genérico do projeto)
```

**Índices/constraints**:

- `uq_role_assignment_invites_pending`: único parcial em
  `(process_instance_id, role_key, email)` **WHERE** `status = 'pending' AND deleted_at IS NULL`
  — impede duas ofertas simultâneas para a mesma pessoa/papel/processo; mesmo padrão do
  índice único parcial de `assignments` (`models.py:1001-1011`). Uma segunda tentativa deve
  ser rejeitada orientando "reenviar o convite existente", não criar um segundo.
- `token_hash` único (não parcial — um hash de token nunca deve colidir entre convites,
  vivos ou não, para eliminar qualquer ambiguidade na busca por aceite).
- FK `process_instance_id`, `laboratory_id`, `created_by`, `accepted_by`, `revoked_by` —
  padrão já usado em todo o resto do schema.

**Transições de `status`**:

```text
pending ──(aceite bem-sucedido, FR-010/FR-011)──► accepted   [terminal]
pending ──(revogação, FR-013)───────────────────► revoked    [terminal]
pending ──(reenvio, FR-012)─────────────────────► pending    [token_hash/expires_at atualizados, mesma linha]
```

Não existe transição para `accepted` ou `revoked` a partir de outro estado que não
`pending`; a camada de serviço rejeita reenvio/revogação/aceite quando `status != 'pending'`
(FR nos endpoints, ver `contracts/`).

## 2. `ProcessParticipantInvite` × `Assignment` (Spec 006, inalterada)

O aceite de um convite (FR-011) cria uma `Assignment` pelo **mesmo código** de
`create_participant` — não uma tabela paralela, não uma cópia de regra. O convite guarda só
o que falta antes de existir um usuário (e-mail, prazo, canal); a `Assignment` continua
sendo a única fonte de verdade de "quem ocupa o papel agora" (Spec 006, inalterada — SC-008
da spec).

## 3. `AuditEvent` — `event_type` novos (RF034, mesma tabela, sem coluna nova)

| `event_type` | Quando | `context_data` mínimo |
|---|---|---|
| `INVITE_CREATED` | Convite criado (FR-004/005) | `invite_id`, `role_key`, `email`, `channel` |
| `INVITE_RESENT` | Reenvio (FR-012) | `invite_id`, `previous_expires_at`, `new_expires_at` |
| `INVITE_ACCEPTED` | Aceite bem-sucedido (FR-011) | `invite_id`, `role_key`, `assignment_id` (o novo) |
| `INVITE_REVOKED` | Revogação (FR-013) | `invite_id`, `role_key` |

Sem `INVITE_EXPIRED`: expiração é estado derivado por tempo, não uma ação de alguém — a
trilha já reconstrói isso comparando `expires_at` com o momento da consulta, mesmo
princípio de "Em Atraso" no Kanban (Spec 018).

## 4. Extensão declarativa do template (YAML, sem migração)

Campo novo, opcional, em `phases[].activities[]` — ao lado de `activity_type` (Spec 017):

```yaml
- key: "assign_sponsor"
  name: "Definir o Patrocinador"
  order_index: 1
  assigned_role: "proponent"        # quem executa esta atividade (ActivityCargo já existente)
  activity_type: "role_assignment"  # novo valor do campo já existente
  target_role_key: "sponsor"        # NOVO campo — qual ParticipantRole esta atividade preenche
  dependencies: []
```

`target_role_key` só tem sentido quando `activity_type == "role_assignment"`; obrigatório
nesse caso, ignorado nos demais. Lido do `definition_payload` já congelado por versão
(Spec 004 FR-001/SC-002) — nenhuma coluna nova em `activity_instances` (R5).

As 8 atividades, na ordem e dependência já decididas com o usuário (ver "Sequência de
Preenchimento" no `spec.md`):

| `key` (sugerido) | `assigned_role` (executor) | `target_role_key` | `dependencies` |
|---|---|---|---|
| `assign_sponsor` | `proponent` | `sponsor` | `[]` |
| `assign_group_manager` | `proponent` | `group_manager` | `[]` |
| `assign_sample_selection_group` | `group_manager` | `sample_selection_group` | `[assign_group_manager COMPLETED]` |
| `assign_lead_laboratory` | `group_manager` | `lead_laboratory` | `[assign_group_manager COMPLETED]` |
| `assign_participating_laboratory` | `group_manager` | `participating_laboratory` | `[assign_group_manager COMPLETED]` |
| `assign_statistician` | `group_manager` | `statistician` | `[assign_group_manager COMPLETED]` |
| `assign_collaborator` | `bracvam` | `collaborator` | `[assign_group_manager COMPLETED]` |
| `assign_adhoc_evaluator` | `bracvam` | `adhoc_evaluator` | `[assign_group_manager COMPLETED]` |

`assigned_role` (quem deve agir) usa o vocabulário `ActivityCargo` **já existente** —
nenhum valor novo: `proponent`/`group_manager` já são papéis contextuais válidos,
`bracvam` já é o cargo global válido (Spec 018/023). Confirma o achado do `research.md`
R5: `assigned_role` (executor da atividade) e `target_role_key` (papel concedido) são
sempre campos distintos para esta atividade — nas linhas 1–2 eles até coincidem com o
papel-alvo de forma enganosa (`proponent` executa, mas o alvo é `sponsor`/`group_manager`,
nunca `proponent`).

**Onde declarar**: decisão de conteúdo (Out of Scope da spec) — se num novo template
próprio da Etapa 2 ou como nova fase de `04_validated_method_dossier.yaml` (mesmo padrão
já usado pela Fase 2 placeholder da Spec 017). Resolvido em `tasks.md`/implementação, não
aqui; a tabela acima já é suficiente para qualquer um dos dois.

## 5. `Settings` — campo novo

```python
INVITE_EXPIRATION_HOURS: int = Field(default=1)  # FR-008
```

Mesmo padrão de `ATTACHMENT_MAX_SIZE_MB` (`core/settings.py`) — inteiro simples via `.env`.

## 6. Autorização — função nova em `core/authorization.py`

```python
PROPONENT_MANAGEABLE_ROLE_KEYS = frozenset({'sponsor', 'group_manager'})

async def can_manage_role_assignment(
    session: AsyncSession, user_id: UUID, process_id: UUID, role_key: str
) -> bool:
    if await can_manage_participants(session, user_id, process_id):
        return True
    if role_key in PROPONENT_MANAGEABLE_ROLE_KEYS:
        return await is_active_effective_proponent(session, user_id, process_id)
    return False
```

Substitui a checagem de `can_manage_participants` isolada em toda rota tocada por esta
feature (criação/reenvio/revogação de convite, e a designação direta quando o `role_key`
alvo for `sponsor`/`group_manager`) — ver `research.md` R3.

## 7. Validação de payload (schemas.py)

`InviteCreate` espelha `ParticipantAssignmentCreate` (Spec 006) no que já existe
(`role_key: ParticipantRole`, `laboratory_id` com o mesmo validador condicional) e
acrescenta:

- `email: EmailStr` (Pydantic) — obrigatório, sempre presente (FR-004).
- `channel: Literal['link'] = 'link'` — único valor aceito nesta entrega (FR-006/007);
  qualquer outro valor é `422`, não silenciosamente ignorado, para não mascarar uma
  integração futura mal configurada.

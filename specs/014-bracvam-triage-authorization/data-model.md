# Data Model — Spec 014

Duas mudanças de dados: catálogo RBAC (seed via migração) e uma coluna em
`evaluation_runs`.

## 1. RBAC — perfil e permissão (migração `bracvam_profile_triage_permission`)

### `access_profiles` — nova linha

| Campo | Valor |
|---|---|
| `id` | `00000000-0000-0000-0000-00000000000a` (fixo) |
| `system_key` | `bracvam` |
| `name` | `BraCVAM` |
| `description` | `Equipe do BraCVAM: coordena submissões e conduz a triagem de métodos candidatos.` |

Distinto de `management_group` ("Grupo Gestor", `...0002`) e `reviewer`
("Revisor", `...0006`).

### `permissions` — nova linha

| Campo | Valor |
|---|---|
| `id` | `00000000-0000-0000-0000-00000000010c` (fixo) |
| `code` | `triage.review` |
| `description` | `Conduzir a triagem: parecer de campo, decisão, e ver/comentar a pré-avaliação por IA.` |

### `access_profile_permissions` — novas composições

| `profile` | `permission` | Observação |
|---|---|---|
| `bracvam` | `triage.review` | nova permissão |
| `bracvam` | `ai_evaluations.read` | permissão existente (D2) |
| `bracvam` | `ai_evaluations.manage` | permissão existente (D2) |
| `administrator` | `triage.review` | nova permissão (Administração) |

`administrator` já detém `ai_evaluations.read/manage` (migração `8b701d7bfeae`).

Cada composição com UUID fixo (`...0002xx`), para downgrade determinístico.

### Downgrade (ordem)

1. `DELETE FROM user_access_profiles WHERE profile_id = <bracvam>`
2. `DELETE FROM access_profile_permissions WHERE id IN (<4 composições desta migração>)`
3. `DELETE FROM permissions WHERE id = <triage.review>`
4. `DELETE FROM access_profiles WHERE id = <bracvam>`

Não toca `permissions.ai_evaluations.*` nem a composição
`administrator↔ai_evaluations.*` (são de outra migração).

### Regras de autorização (derivadas, não persistidas)

| Ação | Antes | Depois |
|---|---|---|
| `POST /processes/{id}/triage/reviews` | qualquer `CurrentUser` (+ guarda de conflito) | `triage.review` (+ guarda de conflito) |
| `POST /processes/{id}/triage/decision` | qualquer `CurrentUser` (+ conflito) | `triage.review` (+ conflito) |
| `GET /processes/{id}/pre-evaluation` | proponente ∨ `group_manager` do processo ∨ `ai_evaluations.read` | proponente (próprio) ∨ `triage.review` |
| `POST /processes/{id}/pre-evaluation/{run}/feedback` | `group_manager` do processo ∨ `ai_evaluations.read` (+ conflito) | `triage.review` (+ conflito) |
| Config de avaliações (`/ai-evaluations/**`) | `ai_evaluations.read`/`manage` (Administrador) | idem + perfil `bracvam` |

`is_effective_group_manager` continua existindo para `can_manage_participants`
(designação de participantes) — só sai das guardas de triagem/pré-avaliação.

## 2. `evaluation_runs.evaluated_content_snapshot` (migração `evaluation_run_content_snapshot`)

### Coluna nova

| Campo | Tipo | Nulo | Default | Descrição |
|---|---|---|---|---|
| `evaluated_content_snapshot` | `JSONB` | sim | `NULL` | Conteúdo do formulário que alimentou a IA, capturado no `_execute`. |

Modelo: `EvaluationRun.evaluated_content_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True, default=None)`.

Formato do valor (lista, ordem = ordem de cobertura pelas associações):

```json
[
  {"field_key": "scope_extension_justification",
   "label": "Justificativa da Extensão de Escopo",
   "value": "<valor submetido>"}
]
```

Idêntico ao schema `EvaluatedContentField` (Spec 013). `value` aceita qualquer
JSON (string, número, bool, null) — o que estava no `FormValue`.

### Ciclo de vida

- **Escrita**: uma vez, em `pre_evaluation_service._execute`, imediatamente antes
  de `run.status = 'completed'`. Reaproveita a lógica de `_evaluated_content`
  (campos cobertos por associação ativa; alvo `form`/`process` → todos).
- **Nunca atualizado** — nem em `retry_run` (nova execução = novo snapshot
  próprio), nem em edição de template/associação.
- **Leitura**: `get_pre_evaluation` retorna `run.evaluated_content_snapshot` se
  não-nulo; senão, cai para `await _evaluated_content(session, run)` (execuções
  pré-migração e execuções `failed`).

### Downgrade

`op.drop_column('evaluation_runs', 'evaluated_content_snapshot')` — não remove
linhas de `evaluation_runs`.

## Entidades sem mudança de esquema

- `EvaluationRunItem`, `ReviewerFeedback`, `DirectReviewRequest`,
  `EvaluationDefinition/Version/Criterion/Assignment/Reference` — inalteradas.
- `Assignment` (participantes de processo) — inalterada; `group_manager`
  permanece papel válido, só perde a função de gatekeeper da triagem.

# Phase 1 Data Model: Helper Único de Conclusão de Atividade

Nenhuma entidade nova e nenhuma migração de schema. Esta feature muda a
**cardinalidade de uso** de entidades já existentes para a atividade de
triagem, alinhando-a ao padrão já usado pela submissão da proposta.

## `ActivityRun` (já existente)

| Aspecto | Antes desta feature (triagem) | Depois desta feature (triagem) |
|---|---|---|
| Quantas runs por processo | Sempre 1 (`run_number` fixo em 1, reaproveitada em toda rodada de diligência) | Uma nova run por rodada de diligência, `run_number` incrementando (1, 2, 3...) — igual à submissão |
| `started_at` de uma rodada nova | Não muda (herda o `started_at` da run reaproveitada) | Reflete o início real da nova rodada |
| Runs de rodadas anteriores | N/A (não existiam como entidades distintas) | Preservadas como estão hoje ao serem concluídas: `status='COMPLETED'`, `completed_at` preenchido — nunca reabertas |

## `Task` (já existente)

| Aspecto | Antes desta feature (triagem) | Depois desta feature (triagem) |
|---|---|---|
| Quantas tasks por rodada de triagem | Só a primeira rodada ganha uma `Task`; rodadas seguintes não geram nenhuma | Uma `Task` nova por rodada, com seu próprio `due_date` |
| `title` | `'Realizar Triagem da Proposta'` (fixo) | Mesmo texto, preservado explicitamente (ver `research.md` #3) — não muda para `act.name` |
| `assigned_role` | `'bracvam'` (fixo) | Mesmo valor, agora resolvido por `_resolve_activity_cargo(a_data)` a partir do template (`assigned_role: "bracvam"` já declarado em todos os YAMLs) — resultado idêntico |
| `due_date` | Herdado da run reaproveitada (nunca recalculado após a 1ª rodada) | Calculado a partir do `started_at` da run da rodada corrente, via `_compute_activity_due_date` (mesma fórmula já usada em todo o motor) |

## `ActivityDependency` (já existente, sem alteração)

Nenhuma mudança de dado ou schema. A dependência declarativa da triagem sobre
a submissão (`required_activity_key: proposal_submission`, `required_status:
COMPLETED`, `condition_type: ACTIVITY_COMPLETED`) já existe, idêntica, nos 5
templates YAML (`src/pivma/templates_data/0{1..5}_*.yaml`) — é a mesma linha
já consultada por `_dependency_satisfied` hoje para qualquer outra atividade
dependente. Usada, não criada, por esta feature.

## `AuditEvent` (já existente, sem alteração de schema)

| Aspecto | Antes desta feature (desbloqueio da triagem) | Depois desta feature |
|---|---|---|
| Evento emitido ao destravar a triagem | Nenhum (`_unblock_triage_activity` não grava `AuditEvent`) | `ACTIVITY_UNBLOCKED`, com `context_data={'activity_key': 'triage_evaluation', 'activity_type': ..., 'unblocked_by': 'proposal_submission'}` — mesmo formato já usado para qualquer outra atividade dependente |

## Regra de derivação de `due_date` (reaproveitada, não duplicada)

```
due_date = None                                           se sla_hours is None
due_date = run_started_at (da rodada corrente) + timedelta(hours=sla_hours)   caso contrário
```

Mesma fórmula de `_compute_activity_due_date`, já usada por todo o motor
(Spec 024) — a diferença introduzida por esta feature é que agora ela roda
também para a rodada N da triagem (N > 1), não só para a primeira.

## Sem novas relações, sem nova coluna, sem nova tabela

`ActivityRun`, `Task`, `ActivityDependency` e `AuditEvent` já se relacionam do
jeito necessário para este efeito (1:N de `ActivityInstance` para
`ActivityRun`, 1:N de `ActivityRun` para `Task`). Esta feature só muda
**quantas vezes** esse relacionamento é exercitado para a triagem — de "no
máximo uma vez" para "uma vez por rodada".

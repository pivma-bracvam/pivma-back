# Contrato: Regra de Consolidação da Pré-avaliação

Nenhum endpoint HTTP muda de forma (path, verbo, request/response shape). O
contrato afetado é o **comportamento observável** dos endpoints já existentes
(Spec 013/020), via a função pura `consolidate()` de `src/pivma/ai/consolidation.py`.

## Função pura: `consolidate(items: Sequence[EvaluatedCriterion]) -> Consolidation`

**Input**: sequência de `EvaluatedCriterion(conclusion, severity)`, onde
`conclusion ∈ {'compliant', 'non_compliant', 'partial', 'indeterminate'}` e
`severity ∈ {'info', 'low', 'medium', 'high', 'critical'}`.

**Output**: `Consolidation(result, alerts, summary)`.

| Cenário de entrada | `result` (antes) | `result` (depois desta feature) |
|---|---|---|
| Lista vazia | `positive` | `positive` (inalterado) |
| Todos `compliant` | `positive` | `positive` (inalterado) |
| ≥1 `non_compliant` com severidade `low`/`medium`, resto `compliant` | `positive` | **`negative`** (mudou) |
| ≥1 `non_compliant` com severidade `high`/`critical` | `negative` | `negative` (inalterado) |
| ≥1 `partial`, resto `compliant` | `positive` | **`negative`** (mudou) |
| ≥1 `indeterminate`, resto `compliant` | `positive` | **`negative`** (mudou) |
| Todos `indeterminate` | `positive` | **`negative`** (mudou) |

## Comportamento observável via API (inalterado em forma, mudou em valor)

### `POST` de submissão de formulário (`src/pivma/routers/forms.py`)

- **Request**: inalterado.
- **Response**: inalterada em forma; `pre_evaluation.status` continua
  `"pré-avaliação em andamento"` na resposta imediata (FR-021a da Spec 013,
  inalterado). O resultado consolidado só é conhecido ao final do processamento
  em background — ver endpoint de consulta abaixo.

### `GET /processes/{id}/pre-evaluation` (`src/pivma/routers/pre_evaluation.py`)

- **Response** (`PreEvaluationResponse`): mesmo shape (`consolidated_result`,
  `summary`, `attention_points`, etc.).
- **Mudança de valor**: `consolidated_result` passa a ser `"negative"` em mais
  cenários (qualquer critério não `compliant`, não só severidade alta/crítica);
  `attention_points` (já filtrado por `conclusion != 'compliant'`, independente de
  `is_alert`) pode agora aparecer em relatórios cujo `consolidated_result` é
  `negative` mesmo com severidades baixas — comportamento coerente com o filtro já
  existente, sem mudança de contrato.

### Roteamento pós-processamento (sem endpoint próprio, efeito colateral do worker em background)

- **Antes**: severidade alta/crítica → processo volta para `SUBMISSION`; caso
  contrário → processo avança para `TRIAGE`.
- **Depois**: qualquer critério não `compliant` → processo volta para `SUBMISSION`;
  todos `compliant` → processo avança para `TRIAGE`. Mecanismo de transição
  (`_return_to_proponent`, `_unblock_triage_activity`, `_set_process_status`)
  inalterado — só a condição de entrada muda.

## Compatibilidade

- Nenhum cliente que já lê `consolidated_result` (`'positive'`/`'negative'`) ou
  `attention_points` precisa mudar de parsing — os valores possíveis e o shape são
  os mesmos; só a frequência/condições em que cada valor aparece mudam.
- Execuções históricas (`EvaluationRun` já `completed` antes da entrega) não são
  reprocessadas; suas leituras via `GET .../pre-evaluation` continuam retornando o
  `consolidated_result` já persistido, calculado pela regra antiga (FR-007).

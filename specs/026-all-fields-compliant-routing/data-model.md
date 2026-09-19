# Data Model: Regra de Consolidação "Todos os Campos Conformes"

Esta feature **não introduz nenhuma entidade, tabela, coluna ou migração nova**. Ela
reinterpreta o significado de campos já existentes (definidos nas Specs 013/014/020).
Nenhuma alteração de schema é necessária.

## Entidades existentes cujo significado muda

### `EvaluationRun.consolidated_result` (`str`: `'positive'` | `'negative'`)

- **Antes (Spec 013, FR-030)**: `'negative'` sse existe ao menos um critério com
  `conclusion == 'non_compliant'` e `severity in {'high', 'critical'}`.
- **Depois (esta feature, FR-001)**: `'negative'` sse existe ao menos um critério
  com `conclusion != 'compliant'` (ou seja, `non_compliant`, `partial` **ou**
  `indeterminate`), independentemente de `severity`.
- Sem mudança de tipo, coluna ou índice — apenas do algoritmo que produz o valor.

### `EvaluationRunItem.is_alert` (`bool`)

- **Antes**: `True` quando o critério não era `compliant` **e** não era, sozinho,
  motivo de bloqueio (ex.: não conforme de severidade baixa/média, parcial,
  indeterminado). Sinalizava "ponto de atenção que não impediu o avanço".
- **Depois**: como todo critério não `compliant` agora bloqueia, `is_alert` será
  sempre `False` sempre que a lista de critérios tiver algum item não conforme —
  não existe mais "não conformidade que não bloqueia" nesta pré-avaliação
  automática. O campo é preservado no schema e na API por compatibilidade e para
  eventual reintrodução futura de uma faixa não bloqueante; **não é removido nem
  recalculado retroativamente** para execuções concluídas antes da entrega
  (reafirma FR-007).

### `Consolidation` (dataclass interna de `src/pivma/ai/consolidation.py`)

- `result`: `'positive' | 'negative'` — mesmo campo, novo algoritmo (Decisão 2 do
  `research.md`).
- `alerts: list[bool]` — mesma estrutura; passa a ser, na prática, uma lista onde a
  posição de qualquer item não conforme é sempre `False` (ver acima).
- `summary: dict[str, int]` — inalterado (`total`, `compliant`, `non_compliant`,
  `partial`, `indeterminate`); a contagem por conclusão não depende da regra de
  consolidação.

## Entidades relacionadas que **não** mudam

- `EvaluationRunItem.severity`: continua armazenado e exibido; deixa de ser
  insumo do algoritmo de consolidação, mas segue disponível como metadado e para
  agrupamento visual na triagem (FR-002).
- `EvaluationRun.status`, `ProcessInstance.status`, `DirectReviewRequest`,
  `FieldReview`, `Decision`: nenhuma mudança de estrutura ou de fluxo (FR-004,
  FR-005, FR-009); apenas o gatilho automático que decide o roteamento após a
  pré-avaliação muda.

## Regras de validação/transição afetadas

- Transição `AI_PRE_EVALUATION → TRIAGE` (positivo) ou `AI_PRE_EVALUATION → SUBMISSION`
  (negativo, retorno ao proponente): inalterada em mecanismo; a única mudança é a
  condição que decide qual delas ocorre.
- Nenhuma nova regra de unicidade, obrigatoriedade ou cardinalidade é introduzida.

# Research: Regra de Consolidação "Todos os Campos Conformes"

## Contexto técnico já resolvido (sem NEEDS CLARIFICATION)

A varredura do código confirmou que a mudança é isolada a uma única função pura,
sem impacto de schema/migração. Não há incógnitas de linguagem, storage ou
infraestrutura a pesquisar — o trabalho é de regra de negócio, não de nova
tecnologia. Os pontos abaixo documentam as decisões de design necessárias para o
Phase 1.

## Decisão 1 — Onde a regra muda

- **Decision**: A única alteração de lógica fica em `src/pivma/ai/consolidation.py`,
  na função `consolidate`/`_is_blocking`. Nenhum outro módulo (`pre_evaluation_service.py`,
  `process_engine.py`, `routers/triage.py`) precisa mudar, porque eles já consomem
  `consolidation.result` (`'positive'`/`'negative'`) de forma agnóstica ao critério
  interno de bloqueio.
- **Rationale**: `consolidate()` é a única função que decide `POSITIVE`/`NEGATIVE`
  a partir da lista de `EvaluatedCriterion`; todo o roteamento fixo (`_return_to_proponent`,
  `_unblock_triage_activity`, `request_direct_review`) já opera sobre esse resultado
  consolidado e permanece correto sob a nova regra sem alteração (confirma FR-004,
  FR-005, FR-009 da spec).
- **Alternatives considered**: Duplicar a regra no nível do endpoint/serviço
  (rejeitado — reintroduziria a lógica de decisão fora do módulo dedicado,
  violando a separação já estabelecida na Spec 013); adicionar um flag de
  configuração para alternar entre a regra antiga e a nova (rejeitado — a Spec 013
  já deixou explícito "roteamento fixo e embutido, sem editor de regras nesta
  versão"; esta feature substitui a regra fixa por outra regra fixa, não introduz
  configurabilidade).

## Decisão 2 — Nova predicado de bloqueio

- **Decision**: `_is_blocking(item)` passa a ser `item.conclusion != 'compliant'`
  (bloqueia se não conforme, parcial **ou** indeterminado), removendo a checagem de
  severidade (`item.severity in BLOCKING_SEVERITIES`). `consolidate()` retorna
  `NEGATIVE` se `any(_is_blocking(item) for item in items)`, senão `POSITIVE`. Lista
  vazia continua `POSITIVE` (reafirma FR-006 / edge case "sem avaliações").
- **Rationale**: Implementa diretamente FR-001 e FR-003 da spec (todos conformes ⇒
  positivo; qualquer não conforme/parcial/indeterminado ⇒ negativo, independente de
  severidade).
- **Alternatives considered**: Manter `BLOCKING_SEVERITIES` mas expandi-lo para
  incluir todas as severidades (`{info, low, medium, high, critical}`) em vez de
  remover a checagem — funcionalmente equivalente, mas rejeitado por deixar código
  morto/confuso (uma constante "todas as severidades bloqueiam" não comunica a
  regra tão claramente quanto checar a conclusão diretamente); manter `partial` fora
  do bloqueio (leitura mais branda) — rejeitado, pois a Clarification Q1 da spec 026
  decidiu explicitamente que indeterminado bloqueia, e "parcialmente conforme" é,
  por definição, menos conforme que indeterminado.

## Decisão 3 — Campo `is_alert` / `alerts`

- **Decision**: O campo `EvaluationRunItem.is_alert` e a lista `Consolidation.alerts`
  são mantidos na API e no schema (nenhuma migração, nenhuma mudança de contrato),
  mas seu valor deixa de distinguir "não conforme mas não bloqueante" — como todo
  item não conforme agora bloqueia, `is_alert` será sempre `False` sempre que houver
  qualquer item não conforme na lista (não há mais "não conformidade que não é
  motivo do bloqueio"). Isso é uma consequência aceita da nova regra, não um bug:
  `attention_points` no relatório (`_report_payload`) já filtra por
  `item.conclusion != 'compliant'`, independente de `is_alert`, então a
  apresentação ao proponente/triador (FR-008) não depende desse campo.
- **Rationale**: Evita uma migração de banco e uma mudança de contrato de API só
  para remover um campo que passa a ser trivial; simplicidade (YAGNI) — o campo
  pode voltar a ser útil se uma futura versão reintroduzir uma faixa "alerta, não
  bloqueante" (ex.: severidade baixa com `partial`). Documentado aqui para que a
  implementação e os testes não tratem `is_alert == False` universal como regressão.
- **Alternatives considered**: Remover o campo e a coluna via migração — rejeitado
  por estar fora do escopo (a spec declara explicitamente que não há mudança de
  autorização/estrutura além da regra de consolidação) e por ser trabalho não
  solicitado pelo pedido original do usuário.

## Decisão 4 — Consequência para o painel de triagem em submissões roteadas automaticamente

- **Decision**: Documentar (não implementar nada extra) que, para toda submissão
  que chega à triagem pelo roteamento automático positivo, `attention_points` do
  relatório de pré-avaliação será sempre uma lista vazia (por definição, todos os
  critérios são `compliant`). Non-conforme/parcial/indeterminado só aparecerão no
  painel do triador quando a submissão chegar via **intervenção direta** do
  proponente (US3 da Spec 013), caso em que o relatório original (com os itens
  problemáticos) é preservado e exibido normalmente.
- **Rationale**: Efeito direto e esperado da regra "100% conforme"; relevante para
  quem for escrever/atualizar os testes de integração da triagem, para não
  confundir "lista vazia de pontos de atenção" com um bug de coleta de dados.
- **Alternatives considered**: N/A — é uma decorrência lógica da regra, não uma
  escolha de implementação.

## Testes existentes identificados como impactados (para `/speckit-tasks`)

Levantamento informativo (não normativo) de onde a regra atual está expressa em
teste, para orientar a geração de tasks — não é uma decisão de design:

- `tests/unit/ai/test_consolidation.py`: `test_low_and_medium_non_conformities_stay_positive_as_alerts`,
  `test_only_indeterminate_is_positive` e `test_partial_does_not_block_and_is_alerted`
  fixam explicitamente o comportamento antigo e precisam ser reescritos para a nova
  regra; `test_negative_only_with_high_or_critical_non_conformity`,
  `test_critical_non_conformity_is_negative`, `test_blocking_item_is_not_flagged_as_mere_alert`,
  `test_summary_counts_each_conclusion` e `test_empty_input_is_positive` continuam
  válidos ou precisam apenas de pequenos ajustes de asserção sobre `alerts`.
- `tests/unit/ai/test_pipeline_targets.py::test_document_target_is_indeterminate_without_model_call`:
  também fixava `consolidated_result == 'positive'` para um único critério
  indeterminado; corrigido para `'negative'` durante a implementação (não estava
  listado nas tasks originais).
- `tests/integration/ai/test_run_pre_evaluation.py`: os testes existentes
  (`test_execute_persists_items_and_report_and_routes_negative`,
  `test_execute_positive_result_unblocks_triage`) já usam declarações
  compliant/non-compliant (não dependem de severidade isolada) e devem continuar
  passando sem alteração; vale adicionar um caso novo que prove a mudança de
  comportamento (severidade baixa não conforme agora nega).

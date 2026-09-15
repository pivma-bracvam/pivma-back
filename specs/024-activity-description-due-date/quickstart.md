# Quickstart: Validar o `due_date` Real das Atividades

**Feature**: 024-activity-description-due-date

## Pré-requisitos

- API rodando localmente (`poe serve`), sem migração nova a aplicar —
  `Task.due_date` já existe na tabela `tasks`.
- Seed do Kanban já executado: `python -m scripts.seeds.seed_kanban` (cria
  centenas de processos, vários deles com `proposal_submission`
  (`sla_hours=168`) ou `triage_evaluation` (`sla_hours=72`) em andamento —
  nenhuma alteração no seed é necessária para esta feature).
- Navegador para abrir `demos/kanban/index.html`.

## Passos

1. Abrir `demos/kanban/index.html` e confirmar, como hoje, que os cards
   trazem `sla_hours`/`run_started_at` e são classificados em
   `NAO_INICIADO`/`EM_ANDAMENTO`/`EM_ATRASO`/`CONCLUIDO`.
2. Escolher um card em `EM_ANDAMENTO` ou `EM_ATRASO` (atividade com
   `sla_hours` declarado) e anotar seu `process_id`/`activity_key`.
3. Chamar `GET /tasks?process_id={process_id}` (ou pelo botão equivalente
   estendido na demo) → confirmar que o item correspondente traz
   `due_date` preenchido (não `null`), igual a
   `run_started_at + sla_hours`.
4. Pegar o `id` dessa tarefa e chamar `GET /tasks/{id}` → confirmar que o
   detalhe também retorna `due_date` preenchido (campo novo neste endpoint).
5. Repetir os passos 3–4 para uma atividade sem `sla_hours` declarado (se
   existir alguma no template usado) → `due_date` deve vir `null` nos dois
   endpoints, sem valor inventado.
6. Comparar o `due_date` obtido com a classificação de coluna do card
   (passo 1): um card em `EM_ATRASO` deve ter `due_date` no passado; um card
   em `EM_ANDAMENTO` deve ter `due_date` no futuro — confirma FR-003 (sem
   divergência entre o indicador ao vivo do kanban e o valor persistido).

## Verificação de não regressão

- Uma tarefa criada **antes** desta mudança (dado semeado por uma execução
  anterior do banco, se aplicável) continua com `due_date = null` até ser
  concluída e reaberta em um novo ciclo — confirma que não há backfill (spec,
  Clarifications).
- A suíte automatizada completa (`poe test`) permanece verde, incluindo os
  testes existentes de `classify_kanban_column` e da criação de `Task` em
  `_init_first_activity`/`_activate_activity` — nenhuma regressão na
  classificação de "em atraso" já validada pela Spec 018.

## Critério de conclusão

Este quickstart só é considerado cumprido quando os 6 passos acima forem
executados manualmente contra a API real (não mocada) e a verificação de não
regressão passar — consistente com o critério de conclusão do `AGENTS.md`
(demonstração funcional, sem endpoint criado só para viabilizar a demo).

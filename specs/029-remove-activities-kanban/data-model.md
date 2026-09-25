# Data Model: Remover o Kanban de Pendências

Nenhuma entidade, tabela, coluna, índice ou constraint muda. Nenhuma
migration é criada, e migrations existentes não são editadas.

O Kanban só lia estas entidades, que continuam iguais e em uso pelo motor de
processos e pelo `/tasks`:

- **ProcessInstance**: processo, filtrado pela regra de visibilidade.
- **ActivityInstance**: atividade do processo, com `status` e `blocked_reason`.
- **ActivityRun**: execução da atividade, com `started_at`.
- **ActivityDependency**: dependência entre atividades.
- **Task**: tarefa gerada pela run, com `assigned_role` e `due_date`.
- **Assignment** / **UserAccessProfile** / **AccessProfile**: ocupantes de
  cargos contextuais e globais.

A classificação em colunas (`NAO_INICIADO`, `EM_ANDAMENTO`, `EM_ATRASO`,
`CONCLUIDO`) era calculada na leitura e nunca foi persistida.

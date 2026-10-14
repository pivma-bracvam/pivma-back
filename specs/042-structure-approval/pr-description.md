## Resumo

Fecha a #27. Antes de um processo novo chegar à Etapa 3, o BraCVAM confere
a equipe e as amostras montadas na Etapa 2 e aprova ou reprova cada ponto.
Sem a aprovação, nenhum laboratório recebe frascos.

Spec, plano e tarefas: `specs/042-structure-approval/`.

## Antes de revisar: o plano estatístico e a #25

A #27 lista três coisas para o BraCVAM auditar: os papéis, as amostras e o
plano estatístico. Esta PR audita só as duas primeiras, por uma razão que
vale entender antes de ler o código.

- **Situação da #25.** O plano estatístico viria da Análise Estatística
  (#25). Na atualização de 2026-10-04, a própria #27 registrou que a #25
  saiu do escopo e pediu que se decidisse se a homologação ainda exigiria
  esse plano.
- **O que encontramos no código.** Nada no sistema produz um plano
  estatístico. Não existe atividade, formulário nem artefato para isso nos
  cinco templates. Exigir o plano travaria todo processo novo na Etapa 2,
  sem caminho para destravar.
- **Decisão.** Confirmada em 2026-10-14 e registrada nas Clarifications da
  spec e em `docs/observacoes-e-pendencias.md` (seção "Homologação da
  estrutura (issue #27)", decisão 1): a homologação confere as nove
  atividades da Etapa 2, que são as oito atribuições de cargo e a definição
  das amostras. O plano estatístico fica como pendência aberta nesse mesmo
  arquivo.
- **Como reincluir.** Quando a #25 voltar, a atividade nova entra no YAML
  dos templates como dependência de `structure_approval`. O painel lê os
  pontos das dependências da atividade, sem lista fixa de chaves no código,
  então o plano estatístico vira mais um ponto auditado sem mudar o
  serviço. Falta decidir só as regras de pendência próprias dele.

## O que muda

- **Templates.** Os cinco ganham a atividade `structure_approval` no fim da
  fase 2, editada pelo cargo BraCVAM. Ela depende das nove atividades da
  etapa, e o recebimento de amostras passa a depender dela, não mais da
  definição das amostras. As versões sobem: 01, 02, 03 e 05 para 5, e 04
  para 7. Processos já criados continuam no fluxo antigo.
- **`GET /processes/{id}/structure-approval`.** Painel com os pontos, as
  designações ativas de cada cargo, as contagens das amostras, as
  pendências e o histórico de decisões. O painel não mostra nome químico,
  CAS, SDS nem código cego. As pendências são calculadas na hora: atividade
  não concluída, cargo sem designação ativa, laboratório participante sem
  códigos e códigos de laboratório que saiu do estudo.
- **`POST /processes/{id}/structure-approval/decision`.**
  - Aprovar exige justificativa e nenhuma pendência; o recebimento abre em
    cada laboratório com códigos.
  - Reprovar exige justificativa e um motivo por ponto. Cada ponto ganha
    uma execução nova, com tarefa para o responsável, e a execução anterior
    continua concluída. A homologação reabre sozinha quando o último ponto
    reprovado conclui.
- **Auditoria.** A decisão fica em `decisions` (`decision_type`
  `STRUCTURE_APPROVAL`), com os pontos reprovados na coluna nova
  `rejected_points` (JSONB). A migração `a3d5f7b9c1e2` é reversível. A
  linha do tempo ganha `STRUCTURE_APPROVED`, `STRUCTURE_REJECTED` e
  `ACTIVITY_REOPENED`. O responsável pelo ponto lê o motivo no
  `ACTIVITY_REOPENED`; os eventos da decisão ficam visíveis só para Admin e
  BraCVAM.
- **Autorização.** Admin e BraCVAM veem o painel. Só o BraCVAM sem conflito
  de interesse decide. Quem não vê a homologação recebe `404`.
- **Concorrência.** Duas decisões simultâneas terminam com uma gravada e a
  outra recusada com `409`.

## Outras decisões registradas

Todas em `docs/observacoes-e-pendencias.md` e nas Clarifications da spec.

- **Trava do template de coleta.** Substitui a decisão 5 da #26. O template
  trava quando a Etapa 3 de um processo vinculado começa, isto é, na
  primeira execução de uma atividade da fase 3. Antes travava na conclusão
  das amostras, que agora a homologação pode reabrir. Excluir o processo
  antes da Etapa 3 não trava o template.
- **Fechamento da atribuição de cargo.** Uma atribuição reaberta conclui na
  próxima designação ou revogação do cargo, quando sobra ao menos uma
  designação ativa e nenhum convite pendente. Não existe rota de conclusão.
- **Convite criado depois da conclusão.** Não reabre a atribuição nem
  bloqueia a homologação. O BraCVAM decide pelas designações ativas e pelas
  amostras no momento da decisão.

## Defeitos corrigidos no caminho

Cada um tem teste que falhava antes da correção.

- **Dependente bloqueado para sempre.** Quando os dois últimos
  pré-requisitos de uma atividade concluíam em transações simultâneas, cada
  uma lia a outra em andamento, e o dependente nunca abria.
  `_advance_dependent_activities` agora trava e relê o dependente antes de
  conferir as dependências. O defeito já existia na abertura de
  `sample_definition`; reprovar dois pontos o tornaria comum.
- **Cargo concluído sem ninguém.** Revogar o único convite pendente de um
  cargo vazio concluía a atribuição sem designação. Agora a conclusão exige
  ao menos uma designação ativa.

## Testes

- **Jornadas** em
  `tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`:
  - aprovar e liberar o recebimento;
  - reprovar, ver a atividade voltar, reexecutar e aprovar (critério de
    conclusão da issue);
  - aprovação recusada antes da abertura, com pendência e por quem não
    decide.

  As três partem do bootstrap canônico e usam só a API: cadastro, login,
  concessão de perfil e cadastro institucional.
- **Focados** em `tests/api/routers/test_structure_approval_*.py`: painel,
  aprovação, reprovação, validação, cada pendência, segurança e cegamento,
  visibilidade na linha do tempo, concorrência e processo cancelado.
- **Regressões:** fechamento na revogação e convite em
  `test_participant_router.py` e `test_invites_router.py`. Trava do
  template em `test_collection_template_lock.py` e
  `test_collection_template_concurrency.py`. Concorrência do motor em
  `tests/integration/database/test_dependency_release_concurrency.py`.
- **Migração** em
  `tests/integration/migrations/test_decision_rejected_points_migration.py`.
- As jornadas do recebimento e do template de coleta passam pela
  homologação.

## Documentação

- Tutorial novo: `manual/tutorial/homologacao-da-estrutura.md`. O tutorial
  da equipe passa a designar os oito cargos.
- Referências atualizadas: rotas, erros, eventos, estados, templates e
  perfis.
- Explicações atualizadas: processo, escopo, amostras cegas e isolamento.
- Guias afetados também atualizados.

## Verificação

- `poe lint`: sem erros.
- `pytest` completo: 2104 aprovados, 1 ignorado, nenhuma falha. A base
  (`develop` em e0ca7e9) tinha 2026 aprovados e 1 ignorado.
- `poe docs-build` (modo estrito): sem erros.
- `alembic upgrade head`, `downgrade -1` e `upgrade head` num PostgreSQL 17
  descartável: sem erros.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

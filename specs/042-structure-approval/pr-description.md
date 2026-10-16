## Resumo

Fecha a #27. Antes de um processo novo chegar à Etapa 3, o BraCVAM confere
a equipe, o plano estatístico e as amostras montadas na Etapa 2 e aprova ou
reprova cada ponto. Sem a aprovação, nenhum laboratório recebe frascos.

Spec, plano e tarefas: `specs/042-structure-approval/` (a revisão está na
Fase 9 do `tasks.md`).

## Atendimento à revisão de 2026-10-16

As decisões 1, 2 e 5 de `docs/observacoes-e-pendencias.md` (seção da #27) e
as Clarifications da spec (sessão 2026-10-16) registram as duas mudanças.

### 1. Plano estatístico na homologação

| Pedido | Feito |
|---|---|
| Atividade nova na fase 2, do Estatístico, que abre quando ele é designado | `statistical_plan` nos cinco templates, dependente de `assign_statistician` |
| Formulário com anexo obrigatório e resumo curto | `statistical_plan_v1`: `plan_file` (PDF ou DOCX, obrigatório) e `summary` (opcional) |
| `structure_approval` depende dela; o plano vira ponto do painel | A homologação passa a ter dez pontos. O serviço do painel não mudou |
| A reprovação cria formulário novo e guarda o anterior | Coberto por teste. O BraCVAM lê o plano reprovado com `?run_number=N` no formulário e no download do anexo |
| O envio do formulário fica restrito à proposta: sem dossiê, sem IA, sem triagem | Os efeitos da proposta só valem para `proposal_submission`. Os demais formulários gravam `FORM_SUBMITTED` e liberam as dependentes. Um teste liga a IA no formulário do plano e confirma que a triagem não muda |
| IA no plano (opcional) | Ficou de fora, registrada como pendência na seção da #27 |
| Atualizar a decisão 1 e as Clarifications | Feito. A decisão 2 também mudou, de nove para dez pontos |

### 2. Troca de pessoa num cargo reprovado

| Pedido | Feito |
|---|---|
| A atribuição reaberta não fecha sozinha quando entra alguém | Designar e revogar não fecham mais a execução reaberta. Na primeira execução, nada muda |
| Um passo em que a gestora diz que terminou | `POST /processes/{id}/participants/roles/{role_key}/complete`, com a mesma autorização de designar o cargo |
| Atualizar a decisão 5 | Feito |
| Teste de designar a nova antes de revogar a antiga | `test_swap_designating_before_revoking_completes_with_only_the_new`. A jornada 2 também faz a troca nessa ordem |

A declaração é recusada com `409 role_without_designation` (cargo vazio),
`409 pending_invites` (convite pendente), `409 invalid_transition`
(atribuição fora de andamento), `403` (sem autorização para o cargo ou com
conflito de interesse vigente) e `409 process_closed` (processo encerrado).

### Além do pedido

- **`submit_proposal_form` virou `submit_activity_form`.** A função passou a
  enviar qualquer formulário, e o nome antigo confundia.
- **Evento `ROLE_ASSIGNMENT_COMPLETED`.** Registra quem declarou a conclusão
  do cargo reaberto, com `activity_key`, `role_key` e `run_number`.
- **Conflito de interesse na declaração.** Quem tem conflito vigente no
  processo recebe `403`, como na edição das demais atividades.
- **Consulta de execuções anteriores do formulário** (`run_number`), para o
  BraCVAM ler o plano que reprovou. Vale para qualquer formulário, com as
  mesmas permissões de leitura.
- **Guia novo** `manual/guias/enviar-o-plano-estatistico.md`.

### Pontos de atenção

- A gestora pode declarar a conclusão com a pessoa antiga e a nova ativas ao
  mesmo tempo, e o painel não acusa. Não criei pendência para cargo com mais
  de uma pessoa porque laboratórios participantes e colaboradores aceitam
  várias.
- O painel mostra o plano só pelo estado e pelas pendências. O conteúdo fica
  no formulário da atividade.
- Designar e revogar continuam sem checar conflito de interesse. Isso é
  anterior a esta PR e ficou fora dela.

## O que muda

- **Templates.** Os cinco ganham, na fase 2, o plano estatístico
  (`statistical_plan`) e a atividade `structure_approval`, que fecha a fase
  e é editada pelo cargo BraCVAM. Ela depende das dez atividades da etapa,
  e o recebimento de amostras passa a depender dela, não mais da definição
  das amostras. As versões sobem: 01, 02, 03 e 05 para 5, e 04 para 7.
  Processos já criados continuam no fluxo antigo.
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
- **`POST /processes/{id}/participants/roles/{role_key}/complete`.**
  Conclui a atribuição de cargo reaberta (ver acima).
- **Formulários.** `submit_activity_form` envia qualquer formulário; dossiê,
  IA e triagem só na proposta. `GET .../form` e o download de anexo aceitam
  `run_number`.
- **Auditoria.** A decisão fica em `decisions` (`decision_type`
  `STRUCTURE_APPROVAL`), com os pontos reprovados na coluna nova
  `rejected_points` (JSONB). A migração `a3d5f7b9c1e2` é reversível. A
  linha do tempo ganha `STRUCTURE_APPROVED`, `STRUCTURE_REJECTED`,
  `ACTIVITY_REOPENED`, `FORM_SUBMITTED` e `ROLE_ASSIGNMENT_COMPLETED`. O
  responsável pelo ponto lê o motivo no `ACTIVITY_REOPENED`; os eventos da
  decisão ficam visíveis só para Admin e BraCVAM.
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
  `tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`,
  todas a partir do bootstrap canônico e só pela API:
  - aprovar e liberar o recebimento;
  - reprovar o ponto dos laboratórios, trocar o laboratório (designando o
    novo antes de revogar o antigo), declarar a conclusão, refazer as
    amostras e aprovar (critério de conclusão da issue);
  - aprovação recusada antes da abertura, com pendência e por quem não
    decide;
  - a estatística envia o plano, o BraCVAM o reprova, ela envia outro num
    formulário novo e o BraCVAM aprova.
- **Plano estatístico** em `test_structure_approval_statistical_plan.py`:
  tarefa aberta na designação, envio sem anexo recusado, envio com anexo,
  envio sem efeitos da proposta com IA configurada, ponto pendente no
  painel, formulário novo na reprovação e leitura da execução anterior.
- **Atribuição reaberta** em `test_participant_router.py`: designar e
  revogar não fecham, a troca em qualquer ordem, a declaração com evento e
  cada recusa dela, inclusive por conflito de interesse.
- **Homologação** em `tests/api/routers/test_structure_approval_*.py`:
  painel, aprovação, reprovação, validação, cada pendência, segurança e
  cegamento, visibilidade na linha do tempo, concorrência e processo
  cancelado.
- **Regressões:** convites em `test_invites_router.py`; trava do template
  em `test_collection_template_lock.py` e
  `test_collection_template_concurrency.py`; concorrência do motor em
  `tests/integration/database/test_dependency_release_concurrency.py`;
  migração em
  `tests/integration/migrations/test_decision_rejected_points_migration.py`.
  As jornadas do recebimento e do template de coleta passam pela
  homologação.

## Documentação

- Tutoriais: `homologacao-da-estrutura.md` (novo, com a declaração de
  conclusão do cargo) e `equipe-e-amostras.md` (designa os oito cargos e
  envia o plano).
- Guias: `enviar-o-plano-estatistico.md` (novo) e
  `designar-participantes.md` (conclusão da atribuição reaberta).
- Referências: rotas, erros, eventos, estados, templates e perfis.
- Explicações: modelo de processo, escopo, amostras cegas e isolamento.

## Verificação

- `poe lint`: sem erros.
- `pytest` completo: 2125 aprovados, 1 ignorado, nenhuma falha. A base (`develop` em e0ca7e9) tinha
  2026 aprovados e 1 ignorado.
- `poe docs-build` (modo estrito): sem erros.
- `alembic upgrade head`, `downgrade -1` e `upgrade head` num PostgreSQL 17
  descartável: sem erros. A revisão não tem migração nova.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

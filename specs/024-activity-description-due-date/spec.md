# Feature Specification: Prazo Real (due_date) das Atividades

**Feature Branch**: `024-activity-description-due-date`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Quero resolver isso 'description ausente e due_date morto'"

## Contexto

A estrutura comum de atividade (Spec 004/017) já cobre status, tipo,
dependência e ciclo de execução para qualquer `activity_type`. Na revisão
dessa estrutura, duas lacunas concretas foram identificadas: a ausência de
uma descrição por atividade, e o campo de prazo (`due_date`) que nunca é
preenchido.

Esta spec cobre **só a segunda lacuna** (`due_date`), com uma implementação
deliberadamente básica: o objetivo principal é servir de referência concreta
("molde") para as issues que vão organizar o restante do trabalho sobre a
estrutura de atividades, não entregar a versão completa e definitiva do
recurso. A lacuna de descrição por atividade **não é implementada** nesta
spec — fica registrada abaixo, em "Contexto para a Issue", só para dar
contexto a quem for desenvolvê-la depois.

## Clarifications

### Session 2026-09-15

- Q: A descrição de atividade (lacuna 1) deve ser implementada nesta spec? → A: Não. Fica fora da implementação; a lacuna é só documentada como contexto para a issue correspondente, sem User Story, FR ou critério de aceite aqui.
- Q: O ajuste de `due_date` deve preencher retroativamente atividades que já estão em andamento hoje? → A: Não. Vale só para atividades ativadas a partir desta mudança; nenhuma migração de backfill é necessária.
- Q: Identificadores técnicos (nomes de campo, eventos, etc.) devem usar termos em português ou seguir a convenção já existente? → A: Seguir a convenção já existente — identificadores técnicos em inglês (`due_date`, `sla_hours`, `activity_type`, `ActivityRun`); só a prosa da especificação e da issue fica em português.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar o prazo real de uma tarefa em andamento (Priority: P1)

Uma pessoa responsável por uma tarefa, ou alguém que gerencia o processo,
consulta uma atividade em andamento e precisa saber até quando ela deve ser
concluída — uma data concreta, não apenas um indicador de "em atraso" já
calculado silenciosamente pelo sistema.

**Why this priority**: É o único objetivo desta spec. A ausência de uma
data-limite persistida obriga quem depende desse dado a recalculá-lo a partir
do início da execução e do SLA do template — hoje só a classificação de
coluna do kanban faz esse cálculo, ao vivo, e nenhum outro consumidor tem
acesso ao resultado.

**Independent Test**: Ativar uma atividade cujo template declara `sla_hours`,
confirmar que a tarefa correspondente passa a expor uma data-limite concreta e
que essa data é consistente com a classificação "em atraso"/"no prazo" já
existente no kanban para a mesma atividade.

**Acceptance Scenarios**:

1. **Given** uma atividade cujo template declara `sla_hours`, **When** essa
   atividade é ativada (primeira atividade do processo ou desbloqueada por
   dependência) a partir desta mudança, **Then** a tarefa criada para ela
   expõe uma data-limite concreta, calculada a partir do início da execução e
   do prazo declarado.
2. **Given** uma atividade cujo template não declara `sla_hours`, **When** ela
   é ativada, **Then** a tarefa correspondente não expõe uma data-limite
   fabricada — permanece sem prazo, como hoje.
3. **Given** uma tarefa com data-limite já calculada, **When** a classificação
   de "em atraso" da atividade é consultada (kanban ou qualquer outra tela),
   **Then** o resultado é o mesmo que seria obtido comparando a data-limite
   persistida com o momento da consulta — não há divergência entre o dado
   persistido e o indicador calculado.

### Edge Cases

- Uma atividade é reativada em um novo ciclo de execução (nova `ActivityRun`)
  depois de retrabalho: a data-limite da nova tarefa é calculada a partir do
  início desse novo ciclo, não herdada do ciclo anterior — isso já é coberto
  naturalmente por FR-001, sem lógica extra por não ser o primeiro ciclo.
- Um template é republicado com uma nova versão alterando o prazo de uma
  atividade: processos já instanciados a partir de versões anteriores mantêm
  o prazo da versão usada na sua criação, sem alteração retroativa (mesma
  garantia de imutabilidade de versão já aplicada às demais informações da
  definição).
- Uma atividade concluída antes do prazo, ou sem prazo declarado, nunca é
  exibida como "em atraso".
- Uma atividade já em andamento **antes** desta mudança permanece sem
  data-limite persistida até ser concluída e reaberta num novo ciclo — não há
  backfill (ver Clarifications).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE calcular e persistir uma data-limite concreta
  para toda tarefa cuja atividade declare um prazo (SLA) no template, no
  momento em que essa atividade é ativada (primeira atividade do processo, ou
  atividade desbloqueada por dependência), a partir desta mudança em diante.
- **FR-002**: O sistema NÃO DEVE atribuir data-limite a tarefas cuja atividade
  não declare prazo no template — a ausência de prazo continua representando
  "sem prazo definido", nunca um valor inferido.
- **FR-003**: O sistema DEVE manter a classificação de atividade "em atraso"
  (hoje calculada ao vivo a partir do prazo declarado e do início da
  execução) consistente com a data-limite persistida — as duas fontes nunca
  podem divergir para a mesma atividade.
- **FR-004**: O sistema DEVE preservar o prazo declarado na versão do
  template usada para criar um processo, mesmo que uma versão mais recente do
  mesmo template altere esse valor (garantia de imutabilidade de versão já
  aplicada às demais informações da definição).

> Fora de escopo, por decisão registrada em Clarifications: preencher
> retroativamente a data-limite de atividades cujo ciclo de execução já
> estava em andamento antes desta mudança (sem backfill/migração de dados).

### Key Entities *(include if feature involves data)*

- **Tarefa**: representação executável de uma atividade em andamento — passa
  a carregar uma data-limite concreta e coerente com o prazo declarado, em
  vez de um campo sempre vazio.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Toda atividade ativada a partir desta mudança, cujo template
  declara prazo, expõe uma data-limite concreta, verificável sem que a pessoa
  usuária precise calcular manualmente a partir do início da execução e do
  SLA.
- **SC-002**: A classificação de "em atraso" permanece idêntica, atividade por
  atividade, à observada antes desta mudança — zero regressões na
  identificação de atraso em uma comparação antes/depois.
- **SC-003**: Templates publicados antes desta capacidade continuam
  instanciando processos normalmente sem qualquer edição manual — 0 templates
  existentes precisam ser alterados para continuar funcionando.

## Assumptions

- Escopo deliberadamente básico: o objetivo é ter uma referência concreta e
  pequena de implementação para orientar as issues futuras, não esgotar o
  tema de prazos/SLA.
- A data-limite é derivada exclusivamente do prazo (SLA) já declarado no
  template e do início do ciclo de execução vigente — esta spec não introduz
  uma forma nova de declarar prazo, só passa a persistir o resultado do
  cálculo que já existe hoje de forma implícita.
- Tarefas de atividades sem prazo declarado continuam sem data-limite
  indefinidamente — não há prazo padrão implícito para quem não declarou um.
- Sem backfill: atividades já em andamento antes desta mudança não recebem
  data-limite retroativa (ver Clarifications).
- Prosa da especificação e da issue em português; identificadores técnicos
  (nomes de campo, eventos, chaves) seguem a convenção já existente do
  projeto, em inglês.
- Esta spec cobre apenas a estrutura comum de atividade (o que hoje já é
  compartilhado por todo `activity_type`); não declara nem depende de nenhuma
  regra de negócio específica dos tipos de atividade ainda não implementados
  (assignment, sample_definition, approval, etc.).
- Implementação prevista diretamente na branch atual (`develop`), sem criação
  de branch de feature dedicado desta vez.
- Contexto a carregar para a issue, fora do escopo desta implementação:
  descrição por atividade. Hoje uma atividade só tem `name` — não existe um
  campo de descrição que explique, para quem vai executá-la ou acompanhá-la,
  o que ela compreende (existe para `process_template` e para `forms`, mas
  não por atividade dentro de uma fase). Essa lacuna não é resolvida nesta
  spec; fica registrada aqui só para ser citada como contexto na issue, para
  quem for desenhar essa capacidade depois.

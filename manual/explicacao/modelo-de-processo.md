# Modelo de processo

Um processo de validação é uma instância de um template. O template define
fases e atividades; o processo guarda o andamento delas.

## Entidades

```mermaid
erDiagram
    TEMPLATE ||--|{ VERSAO : "publica"
    VERSAO ||--o{ PROCESSO : "instancia"
    PROCESSO ||--|{ FASE : ""
    FASE ||--|{ ATIVIDADE : ""
    ATIVIDADE ||--o{ EXECUCAO : "run_number"
    EXECUCAO ||--o{ TAREFA : ""
    EXECUCAO ||--o| FORMULARIO : "valores"
    PROCESSO ||--o{ DESIGNACAO : "cargos"
```

| Entidade | Papel |
|---|---|
| Template e versão | Definição declarativa (YAML). O processo fica na versão em que nasceu. Quando o YAML sai, o bootstrap aposenta o template: ele não aceita processos novos e não aparece em `GET /processes/templates`, mas a lista e o detalhe mostram o tipo dos processos já criados |
| Processo | Título, código, ciclo de vida (`OPEN`, `CLOSED`, `CANCELLED`, `ARCHIVED`) |
| Fase | Agrupa atividades em ordem |
| Atividade | Unidade de trabalho com cargo responsável, concessões de ver/editar, dependências e prazo |
| Execução | Uma tentativa da atividade. Reenvio, revisão ou reabertura criam a seguinte |
| Tarefa | O que aparece em `GET /tasks` para o cargo agir |
| Designação | Liga um usuário a um cargo no processo |

## O processo não guarda a etapa

O `status` do processo diz só se ele está vivo. Onde ele está no fluxo vem
das atividades: várias podem estar abertas ao mesmo tempo (as oito
designações da Fase 2, por exemplo). Por isso o frontend monta o quadro a
partir das tarefas, e não de um campo "etapa atual".

## Como uma atividade abre

```mermaid
stateDiagram-v2
    [*] --> BLOCKED
    BLOCKED --> IN_PROGRESS: todas as dependências COMPLETED
    IN_PROGRESS --> COMPLETED: ação concluída
    COMPLETED --> [*]
```

Ao concluir uma atividade, o motor verifica as que dependem dela. Cada uma
cujas dependências estão todas concluídas abre uma execução com tarefa, e o
evento `ACTIVITY_UNBLOCKED` vai para a linha do tempo. A primeira atividade
da primeira fase abre na criação do processo.

O prazo da tarefa é `sla_hours` somado à abertura da execução.

## Fase 1: submissão e triagem

```mermaid
flowchart LR
    S[proposal_submission] -->|com avaliação de IA| IA{Pré-avaliação}
    S -->|sem avaliação| T[triage_evaluation]
    IA -->|positiva| T
    IA -->|negativa ou falha| R[submission_return_review]
    T -->|NEEDS_REVISION| R
    T -->|REJECTED| X[CLOSED]
    T -->|APPROVED| F2[Fase 2]
    R -->|REVISE| S
    R -->|CONTEST_AI| T
    R -->|WITHDRAW| X
```

`submission_return_review` não tem dependências: nasce bloqueada e o motor a
abre por evento, quando a IA ou a triagem devolvem a submissão.

## Fase 2: composição da governança

A triagem aprovada abre `assign_sponsor` e `assign_group_manager` para o
proponente. Com o Grupo Gestor designado, abrem as demais atribuições. Na
primeira execução, uma atividade de atribuição fecha sozinha numa
designação ou numa revogação, quando o cargo fica com ao menos uma
designação ativa e sem convite pendente. `sample_definition` abre quando o
Grupo de Seleção de Amostras e os laboratórios participantes estão
designados. `statistical_plan` abre quando o Estatístico é designado: ele
envia o plano por um formulário com anexo obrigatório. Detalhes em
[Templates de processo](../referencia/templates.md).

### Homologação da estrutura

A fase termina em `structure_approval`, o portão entre a Etapa 2 e a Etapa
3. Ela abre para o BraCVAM quando as dez atividades anteriores concluem.
Essas dependências são os pontos que o BraCVAM confere no painel
(`GET /processes/{id}/structure-approval`), com as pessoas designadas e as
contagens das amostras.

```mermaid
flowchart LR
    P[Dez pontos concluídos] --> H[structure_approval]
    H -->|APPROVED| E3[Etapa 3]
    H -->|REJECTED| R[Pontos reabertos]
    R -->|último ponto conclui| H
```

- **Pendências**: o painel e a aprovação as calculam no momento. Um ponto
  não concluído, um cargo sem designação ativa, um laboratório participante
  sem códigos cegos ou códigos de um laboratório que saiu impedem a
  aprovação (`409 structure_pending`).
- **Aprovação**: conclui a fase 2 e abre o recebimento em cada laboratório.
- **Reprovação**: o BraCVAM escolhe os pontos e escreve um motivo para cada
  um. Cada ponto ganha uma execução nova, com a tarefa de volta para quem o
  executa; a execução anterior continua concluída. A homologação fica
  bloqueada e reabre sozinha, numa execução nova, quando o último ponto
  reprovado conclui. Dependentes de um ponto reaberto que já tinham
  concluído não mudam.
- **Cargo reaberto**: designar e revogar não fecham a execução reaberta de
  uma atribuição. Quem gere o cargo declara que terminou a correção
  (`POST /processes/{id}/participants/roles/{role_key}/complete`). Assim a
  gestora pode designar a pessoa nova antes de revogar a antiga sem que a
  homologação reabra com as duas no cargo.
- **Plano reaberto**: o Estatístico recebe um formulário novo. O anterior
  continua enviado na execução anterior.
- **Decisões**: ficam em `decisions` com autor, data, justificativa e os
  pontos reprovados, e aparecem no painel e na linha do tempo.

Os processos criados com a versão anterior de cada template não têm a
homologação nem o plano estatístico: neles, a conclusão de
`sample_definition` abre a Etapa 3.

## Fase 3: execução da validação

A aprovação da homologação abre `sample_receipt`, que cada laboratório
participante executa à parte. A execução de um laboratório fecha quando o lote
dele fica completo. Se um frasco chega fora de ordem, o motor abre
`sample_receipt_resolution` para o Grupo de Seleção de Amostras decidir. Veja
[Isolamento por laboratório](isolamento-por-laboratorio.md) e
[Receber amostras](../guias/receber-amostras.md).

`sample_receipt` é a última atividade dos templates. Nenhuma atividade de
ensaio, envio de resultados, estatística ou avaliação ad hoc vem depois dela.
Quando todos os laboratórios fecham o recebimento, o processo continua `OPEN`
e sem tarefa pendente.

## Encerramento

| Ação | Quem | Efeito |
|---|---|---|
| Rejeitar na triagem | BraCVAM | `CLOSED` |
| Desistir na revisão do retorno | Proponente | `CLOSED` |
| Excluir | Proponente ou Admin/BraCVAM, com o processo `OPEN` | `CANCELLED`; fases, atividades, execuções, tarefas e pré-avaliações abertas são canceladas; documentos ficam |
| Arquivar | Quem tem `triage.review`, sem conflito de interesse | `ARCHIVED`, a partir de `CLOSED` ou `CANCELLED` |

Processo encerrado não aceita mutações (`409`). Nenhuma ação encerra o
processo por conclusão da validação: os únicos caminhos para `CLOSED` são a
rejeição na triagem e a desistência do proponente.

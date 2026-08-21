# Diretrizes e Especificações do Projeto

## 1. Objetivo

A Plataforma de Validação e Governança de Métodos Alternativos (PIVMA) deverá fornecer o core de execução, acompanhamento e governança de processos de validação científica.

A plataforma será orientada a instâncias de processos compostas por fases, atividades, execuções de atividades, tarefas, formulários, atribuições, artefatos, aprovações e eventos.

O objetivo é oferecer um mecanismo padronizado para execução dos processos existentes, mantendo flexibilidade controlada para variações de formulários, parâmetros, participantes, amostras, rodadas e dependências.

A infraestrutura transversal de autenticação, usuários, sessões/tokens, RBAC global e auditoria básica é considerada existente.

---

## 2. Princípios arquiteturais

### 2.1 Processo como instância

Cada submissão cria uma `ProcessInstance`.

A instância deve possuir:

- tipo de processo;
- template utilizado;
- versão do template;
- estado atual;
- participantes;
- fases;
- atividades;
- histórico;
- artefatos;
- tarefas;
- decisões.

---

### 2.2 Template versus execução

A definição de um processo deve ser separada de sua execução.

Um `ProcessTemplate` descreve a estrutura reutilizável.

Uma `ProcessInstance` representa um processo concreto.

Uma alteração futura no template não deve modificar silenciosamente uma instância já iniciada.

---

### 2.3 Atividade como unidade de trabalho

Uma `Activity` representa uma unidade de trabalho do processo.

Exemplos:

- submissão;
- triagem;
- seleção de amostras;
- seleção de laboratórios;
- geração de códigos cegos;
- definição de Data Template;
- aprovação;
- execução laboratorial;
- consolidação;
- revisão;
- deliberação.

A atividade define o comportamento esperado, mas sua execução concreta pertence a uma `ActivityRun`.

---

## 3. Activity Run

`ActivityRun` representa uma execução concreta de uma atividade.

Uma mesma atividade pode possuir múltiplas execuções.

Exemplo:

```text
Interlaboratory Execution
    Run #1
        6 samples
        4 laboratories

    Run #2
        40 samples
        8 laboratories
```

Também é possível utilizar múltiplas execuções para tratar reprocessamentos:

```text
Activity 3 — Run #1
Activity 4 — Run #1
Activity 5 — Run #1 — FAILED

Activity 3 — Run #2
Activity 4 — Run #2
Activity 5 — Run #2 — COMPLETED
```

Nenhuma execução anterior deve ser apagada por uma nova execução.

---

## 4. Estados

A máquina de estados deve ser utilizada para controlar estados e transições, sem assumir a responsabilidade de representar toda a lógica do processo.

Estados típicos de atividades:

- `DRAFT`;
- `BLOCKED`;
- `READY`;
- `IN_PROGRESS`;
- `WAITING_APPROVAL`;
- `COMPLETED`;
- `FAILED`;
- `CANCELLED`.

Estados de artefatos podem incluir:

- `DRAFT`;
- `SUBMITTED`;
- `UNDER_REVIEW`;
- `APPROVED`;
- `REJECTED`;
- `SUPERSEDED`.

Estados macro do processo podem incluir:

- `SUBMISSION`;
- `TRIAGE`;
- `PLANNING`;
- `EXECUTION`;
- `REVIEW`;
- `FINAL_DECISION`;
- `CLOSED`.

Os estados exatos devem ser definidos conforme as necessidades funcionais, mantendo a separação entre processo, atividade e artefato.

---

## 5. Dependências

As dependências devem ser representadas como pré-condições de execução.

Uma atividade pode depender de:

- outra atividade;
- execução específica de uma atividade;
- artefato;
- versão de artefato;
- aprovação;
- conjunto de participantes;
- conjunto de amostras;
- resultado válido;
- condição de negócio.

A arquitetura deve preferir dependências orientadas a resultados/artefatos quando a relação exigir maior precisão.

Exemplo:

```text
Sample Selection
    → SampleSelection

Laboratory Selection
    → LaboratorySelection

SampleSelection + LaboratorySelection
    → Generate Blind Codes

Data Template Definition
    → DataTemplate

DataTemplate + Group Manager Approval
    → ApprovedDataTemplate

BlindCodeSet + ApprovedDataTemplate
    → Laboratory Execution
```

---

## 6. Artefatos

Um `Artifact` representa um resultado produzido por uma atividade e que pode ser utilizado por outras atividades.

Exemplos:

- seleção de amostras;
- seleção de laboratórios;
- conjunto de códigos cegos;
- Data Template;
- resultado laboratorial;
- parecer;
- documento técnico;
- relatório;
- arquivo de dados.

Um artefato deve possuir:

- tipo;
- versão;
- estado;
- origem;
- processo;
- atividade/execução que o produziu;
- metadados;
- histórico de alterações;
- informações de aprovação quando aplicável.

---

## 7. Versionamento

Artefatos que possuem significado científico ou regulatório devem ser versionáveis.

Exemplo:

```text
DataTemplate v1
    APPROVED

DataTemplate v2
    DRAFT
```

Se uma execução utilizar `DataTemplate v1`, uma alteração posterior para `v2` não deve alterar retroativamente a execução anterior.

A relação entre execução e artefato deve identificar a versão efetivamente utilizada.

---

## 8. Consumo e produção de artefatos

Cada atividade pode declarar ou possuir:

- entradas;
- saídas;
- regras de validação das entradas;
- regras de disponibilidade;
- condições para utilização das saídas.

Uma atividade só deve iniciar quando suas entradas obrigatórias estiverem disponíveis em estado válido.

Uma atividade pode produzir múltiplos artefatos.

Um artefato pode ser consumido por múltiplas atividades.

---

## 9. Reexecução

A reexecução deve ser tratada como nova execução, e não como rollback destrutivo.

Quando uma atividade ou conjunto de atividades precisar ser repetido:

1. a execução anterior permanece registrada;
2. uma nova execução é criada;
3. as novas entradas são registradas;
4. as novas saídas são vinculadas à nova execução;
5. o sistema registra a justificativa da reexecução;
6. resultados anteriores podem ser marcados como inválidos, substituídos ou mantidos para fins históricos;
7. a consolidação determina quais resultados serão considerados válidos.

A arquitetura não deve impor que toda reexecução reinicie o processo completo.

---

## 10. Rodadas de execução

Atividades repetíveis devem permitir múltiplas rodadas.

Exemplo:

```text
Interlaboratory Study

Round 1
    Samples: 6
    Laboratories: 4

Round 2
    Samples: 40
    Laboratories: 8
```

A definição estrutural da atividade é reutilizada.

Cada `ActivityRun` recebe seus próprios parâmetros e resultados.

Uma rodada pode depender da aprovação ou consolidação de uma rodada anterior.

---

## 11. Templates de processo

A plataforma deverá suportar templates para os principais pipelines:

1. Validação Completa / Desenvolvido;
2. Nova Aplicação / Método Pré-Validado;
3. Novo Sistema Teste / Adaptação Tecnológica;
4. Pipeline Customizado, caso posteriormente necessário.

Os três primeiros devem compartilhar o máximo possível da mesma estrutura.

As diferenças devem ser modeladas principalmente por:

- configuração;
- parâmetros;
- atividades habilitadas;
- formulários;
- regras;
- quantidade de execuções;
- participantes;
- artefatos esperados.

Não deve haver duplicação estrutural desnecessária.

---

## 12. Formulários dinâmicos

Formulários devem ser definidos por templates.

Um `FormTemplate` pode conter campos configuráveis.

Tipos mínimos:

- `text`;
- `integer`;
- `float`;
- `boolean`;
- `select`;
- `date`;
- `file_upload`.

Cada campo pode possuir:

- identificador;
- nome;
- descrição;
- tipo;
- obrigatoriedade;
- ordem;
- unidade;
- precisão;
- opções;
- valor padrão;
- regras de validação;
- dependências;
- versão.

Uma submissão concreta deve ser vinculada a uma versão do formulário.

---

## 13. Validação de formulários

A submissão de um formulário pode passar por múltiplas camadas:

```text
Form Submission
    ↓
Schema Validation
    ↓
Business Validation
    ↓
AI-Assisted Validation
    ↓
Human Review, quando necessário
    ↓
Decision / Completion
```

Validações determinísticas e avaliações de IA devem ser distinguíveis.

Resultados de IA devem ser rastreáveis, incluindo contexto suficiente para identificar:

- qual conteúdo foi avaliado;
- qual avaliação foi produzida;
- quando ocorreu;
- qual componente/versão produziu a avaliação;
- qual decisão humana, se existente, foi tomada posteriormente.

---

## 14. Atribuições locais

O RBAC global existente define permissões gerais.

O processo deve manter uma camada de atribuições locais.

Exemplos:

- Proponente;
- Grupo Gestor;
- Estatístico;
- Grupo de Seleção de Amostras;
- Laboratório Líder;
- Laboratório Participante;
- Comitê Ad-hoc;
- Coordenação.

Uma atribuição deve poder ser:

- criada;
- alterada;
- encerrada;
- consultada;
- auditada.

As atividades podem determinar quais papéis podem executá-las.

---

## 15. Tarefas

As atividades devem ser capazes de gerar tarefas para usuários ou papéis.

Uma tarefa deve possuir:

- processo;
- atividade;
- execução;
- responsável ou papel;
- estado;
- prioridade, quando aplicável;
- prazo, quando aplicável;
- dependências;
- formulário;
- entradas;
- resultados;
- histórico.

A tarefa deve ser a principal unidade de acompanhamento operacional.

---

## 16. Kanban e acompanhamento

A aplicação deve permitir visualizações de tarefas por estado.

Exemplo:

```text
READY
IN_PROGRESS
BLOCKED
WAITING_APPROVAL
COMPLETED
```

A visão individual deve mostrar as tarefas relacionadas ao usuário ou aos papéis que ele exerce.

A visão gerencial deve permitir acompanhar:

- processos;
- fases;
- atividades;
- execuções;
- bloqueios;
- aprovações;
- laboratórios;
- andamento geral.

---

## 17. Bloqueios explicáveis

Quando uma tarefa ou atividade estiver bloqueada, o sistema deve indicar o motivo.

Exemplos:

```text
Bloqueada:
aguardando seleção de laboratórios.

Bloqueada:
aguardando aprovação do Data Template v1.

Bloqueada:
aguardando geração do conjunto de códigos cegos.
```

O bloqueio deve estar relacionado a uma dependência identificável.

---

## 18. Gestão de amostras e cegamento

A seleção de amostras deve produzir um artefato contendo a definição das amostras.

A seleção de laboratórios deve produzir o conjunto de participantes.

A atividade de geração de códigos cegos deve consumir ambos.

O código cego deve ser diferente da identidade real apresentada ao laboratório quando o processo exigir cegamento.

O sistema deve controlar acesso às informações de forma que:

- laboratórios não visualizem a identidade real quando proibido;
- atores administrativos autorizados possam acessar a informação necessária;
- o comitê ad-hoc não visualize identidades protegidas quando a revisão for anônima.

A implementação do cegamento deve considerar controle de acesso no nível de dados, e não somente ocultação na interface.

---

## 19. Alteração do conjunto de laboratórios

Quando um novo laboratório for adicionado ou removido, a arquitetura deve permitir que o conjunto de códigos cegos seja atualizado por uma nova execução ou procedimento definido pela regra do processo.

Exemplo:

```text
Blind Code Generation #1
    Labs A, B, C

Blind Code Generation #2
    Lab D
```

ou, quando a regra científica exigir:

```text
Blind Code Generation #2
    Labs A, B, C, D
    New complete code set
```

A escolha do comportamento deve ser determinada pela regra do processo, sem destruir o histórico anterior.

---

## 20. Data Templates

O Estatístico deve poder criar um template para coleta de resultados.

O template deve definir, quando aplicável:

- campos;
- tipos;
- unidades;
- precisão;
- obrigatoriedade;
- regras de validação;
- estrutura esperada;
- versão.

Após conclusão pelo Estatístico, o template pode entrar em estado de aprovação.

Somente após aprovação do Grupo Gestor a versão aprovada deve estar disponível para atividades que dependam dela.

O mesmo template aprovado pode ser consumido em múltiplas atividades.

---

## 21. Execução laboratorial

Cada laboratório participante deve possuir tarefas próprias quando aplicável.

A execução deve suportar:

### Recebimento

O laboratório confirma:

- recebimento;
- integridade;
- temperatura;
- lacre;
- avarias;
- observações.

Em caso de inconformidade, o sistema deve permitir criar ou ativar uma atividade de tratamento, como reposição de amostras.

### Resultados

O laboratório envia os dados utilizando o Data Template aprovado.

O sistema deve validar a estrutura e os dados conforme as regras definidas.

### Custódia

O laboratório registra:

- devolução;
- descarte;
- quantidade remanescente;
- observações;
- evidências documentais, quando aplicável.

---

## 22. Consolidação

A consolidação não deve assumir que todo resultado produzido pelo processo é válido.

Uma `Consolidation` deve permitir selecionar explicitamente os resultados ou execuções considerados.

Exemplo:

```text
Execution Run #1
    FAILED
    Excluded

Execution Run #2
    COMPLETED
    Included

Execution Run #3
    COMPLETED
    Included
```

A seleção deve ser rastreável.

O sistema deve registrar:

- quem selecionou;
- quando selecionou;
- quais resultados foram selecionados;
- quais foram excluídos;
- justificativas, quando necessárias;
- versão dos artefatos utilizados.

---

## 23. Relatórios

Devem existir pelo menos duas perspectivas.

### Relatório histórico

Deve apresentar o histórico integral:

- atividades;
- tarefas;
- execuções;
- falhas;
- reexecuções;
- decisões;
- aprovações;
- versões;
- arquivos;
- alterações relevantes.

### Relatório de consolidação

Deve apresentar apenas os resultados selecionados como válidos para a finalidade da consolidação.

Os dois relatórios devem derivar dos mesmos dados de origem.

---

## 24. Revisão Ad-hoc

O sistema deve permitir distribuir avaliações independentes para membros de comitês.

Cada avaliador deve possuir sua própria tarefa e submissão.

Quando o processo exigir cegamento, os avaliadores não devem visualizar:

- identidade de outros avaliadores;
- votos de outros avaliadores;
- identidade dos laboratórios protegidos.

A consolidação deve ocorrer somente na etapa apropriada.

Critérios podem incluir:

- reprodutibilidade;
- acurácia;
- aplicabilidade;
- limitações;
- comentários técnicos;
- recomendação.

---

## 25. Governança e Gate Approval

Fases ou atividades críticas podem exigir aprovação formal.

Exemplo:

```text
Data Template
    ↓
Submitted
    ↓
Group Manager Review
    ↓
Approved
    ↓
Available for Laboratory Execution
```

O sistema deve impedir que atividades dependentes de uma aprovação sejam iniciadas antes dela.

---

## 26. Trilha de auditoria

Toda ação relevante deve gerar registro auditável.

O registro deve permitir identificar, no mínimo:

- timestamp;
- usuário;
- processo;
- atividade;
- execução;
- ação;
- resultado;
- metadata/diff relevante;
- origem da ação, quando necessário.

Eventos relevantes incluem:

- criação;
- alteração de estado;
- atribuição;
- remoção de atribuição;
- submissão;
- upload;
- aprovação;
- rejeição;
- reexecução;
- criação de artefato;
- nova versão;
- seleção para consolidação;
- exclusão da consolidação;
- decisão final.

A trilha deve ser tratada como histórico imutável.

---

## 27. Separação entre histórico e estado atual

O estado atual deve permitir consulta eficiente da situação presente.

A auditoria deve preservar o histórico das mudanças.

Uma consulta do estado atual não deve substituir a capacidade de reconstruir o histórico relevante.

---

## 28. Ciclo de vida macro

O processo deve suportar, como estrutura base:

```text
1. Submission
2. Triage
3. Planning and Governance
4. Preparation
5. Interlaboratory Execution
6. Technical Review
7. Consolidation
8. Final Decision
9. Closure
```

As fases podem conter atividades repetíveis e dependentes.

A arquitetura não deve exigir que toda instância percorra cada atividade exatamente uma vez.

---

## 29. Pipeline base

### Fase 1 — Submissão e Triagem

Atividades:

- formulário de submissão;
- revisão campo a campo;
- triagem;
- decisão inicial.

### Fase 2 — Planejamento e Governança

Atividades:

- atribuição de papéis;
- seleção de amostras;
- seleção de laboratórios;
- geração de códigos cegos;
- definição do Data Template;
- aprovação do plano.

### Fase 3 — Execução Interlaboratorial

Atividades:

- recebimento;
- tratamento de inconformidades;
- execução;
- submissão de resultados;
- validação;
- devolução/descarte.

A fase pode conter múltiplas rodadas.

### Fase 4 — Revisão e Deliberação

Atividades:

- revisão Ad-hoc;
- consolidação;
- deliberação;
- relatório de validação;
- encerramento.

---

## 30. Extensibilidade

A arquitetura deve permitir adicionar novos tipos de atividade, formulários e artefatos sem alterar o modelo estrutural principal.

A extensibilidade desejada é controlada.

Não é requisito inicial permitir que usuários finais construam qualquer workflow arbitrário.

A extensão deve ocorrer preferencialmente por:

- novos templates;
- novas atividades;
- novos formulários;
- novos tipos de artefatos;
- novas regras de dependência;
- novos parâmetros.

---

## 31. Requisitos não funcionais

### Rastreabilidade

Todas as decisões e alterações relevantes devem ser rastreáveis.

### Consistência

Uma atividade não deve consumir um artefato inexistente, inválido ou não aprovado quando a aprovação for requisito.

### Segurança

Informações protegidas, principalmente identidade real de amostras e informações submetidas sob cegamento, devem respeitar as permissões aplicáveis.

### Versionamento

Processos e artefatos relevantes devem preservar a versão utilizada na execução.

### Idempotência

Operações críticas devem evitar duplicação acidental de tarefas, artefatos, submissões ou eventos.

### Concorrência

O sistema deve tratar corretamente situações em que múltiplos usuários tentem atuar simultaneamente sobre a mesma atividade ou recurso.

### Observabilidade

Deve ser possível identificar processos bloqueados, atividades pendentes, falhas e inconsistências operacionais.

---

## 32. Modelo conceitual

A estrutura central pode ser representada conceitualmente como:

```text
ProcessTemplate
        ↓
ProcessInstance
        ↓
Phase
        ↓
Activity
        ↓
ActivityRun
   ┌────┼─────────────┐
   ↓    ↓             ↓
Task  FormInstance  Assignment
   │
   ↓
Artifacts
   │
   ├── Inputs
   └── Outputs
        ↓
Dependencies
        ↓
Approvals
        ↓
Consolidation
        ↓
Reports
```

Eventos de domínio e trilha de auditoria acompanham as entidades e ações relevantes.

---

## 33. Exemplo completo de dependências

```text
Select Samples
    ↓
SampleSelection

Select Laboratories
    ↓
LaboratorySelection

SampleSelection + LaboratorySelection
    ↓
Generate Blind Codes
    ↓
BlindCodeSet

Statistician Defines Data Template
    ↓
DataTemplate
    ↓
Group Manager Approval
    ↓
ApprovedDataTemplate

BlindCodeSet + ApprovedDataTemplate
    ↓
Laboratory Preparation
    ↓
Laboratory Execution
    ↓
Laboratory Results

Laboratory Results
    ↓
Technical Review
    ↓
Consolidation
    ↓
Final Decision
```

Se houver falha:

```text
Laboratory Execution #1
    ↓
FAILED

New ActivityRun
    ↓
Laboratory Execution #2
    ↓
COMPLETED
```

A execução #1 permanece no histórico.

---

## 34. Exemplo de reutilização

```text
Activity Definition:
    Interlaboratory Study

Run #1:
    samples = 6
    laboratories = 4
    form_template = PreliminaryResults

Run #2:
    samples = 40
    laboratories = 8
    form_template = FinalResults
```

A mesma definição de atividade é reutilizada.

Os parâmetros, formulários e artefatos utilizados podem variar por execução.

---

## 35. Critérios de aceite do core

O core deverá ser capaz de:

- criar uma instância a partir de um template;
- gerar atividades e tarefas;
- atribuir tarefas a papéis ou usuários;
- bloquear tarefas por dependências;
- liberar tarefas quando dependências forem satisfeitas;
- produzir e consumir artefatos;
- versionar artefatos;
- exigir aprovação quando configurado;
- criar múltiplas execuções da mesma atividade;
- repetir apenas uma parte do processo;
- preservar execuções anteriores;
- suportar formulários configuráveis;
- validar submissões;
- integrar avaliações assistidas por IA;
- controlar informações protegidas por cegamento;
- representar múltiplos laboratórios;
- gerar códigos cegos dependentes dos participantes;
- utilizar Data Templates aprovados em atividades posteriores;
- permitir duas ou mais rodadas de execução;
- selecionar resultados para consolidação;
- manter histórico completo;
- gerar visões operacionais e gerenciais;
- produzir relatórios históricos e consolidados.

---

## 36. Fora do escopo inicial

Não fazem parte do core inicial, salvo necessidade identificada durante a implementação:

- construção de um editor visual genérico de workflows;
- linguagem de regras configurável pelos usuários;
- workflow arbitrário criado por usuários finais;
- substituição do RBAC global existente;
- reconstrução completa da infraestrutura de autenticação;
- escolha obrigatória de tecnologia específica;
- automação completa de decisões científicas por IA;
- implementação de todos os possíveis pipelines futuros.

---

## 37. Diretriz final

A solução deve ser entendida como um **motor de execução e governança de atividades orientado a processos, dependências, artefatos e execuções versionadas**.

A State Machine deve controlar estados.

O mecanismo de atividades deve controlar trabalho.

As dependências devem controlar disponibilidade.

Os artefatos devem transportar resultados entre atividades.

Os Activity Runs devem permitir repetição sem apagar histórico.

Os formulários devem controlar a coleta estruturada de dados.

As atribuições devem controlar responsabilidades locais.

As aprovações devem controlar gates de governança.

A consolidação deve determinar quais resultados são considerados válidos.

A auditoria deve preservar o que efetivamente ocorreu.

Essa separação deve permitir que o sistema permaneça simples o suficiente para o MVP, sem impedir evolução futura para processos mais complexos.

# Contexto, Problemas, Objeções e Limitações do Projeto

## 1. Objetivo do documento

Este documento consolida o contexto funcional e arquitetural da Plataforma de Validação e Governança de Métodos Alternativos (PIVMA), com foco nos problemas que a arquitetura do core da aplicação precisa resolver.

A infraestrutura transversal de usuários, autenticação, sessões/tokens, RBAC global e auditoria básica já existe e não faz parte do escopo principal desta etapa.

O objetivo deste documento é registrar o problema antes da implementação, evitando que decisões arquiteturais sejam tomadas apenas em função de detalhes de implementação.

---

## 2. Contexto do domínio

A PIVMA deverá apoiar processos científicos e regulatórios relacionados à validação de métodos alternativos ao uso de animais em testes de segurança e eficácia.

Cada submissão origina uma instância de processo que percorre atividades de submissão, triagem, planejamento, preparação, execução interlaboratorial, revisão técnica e deliberação final.

O processo precisa ser:

- rastreável;
- auditável;
- reproduzível;
- governável;
- adequado à execução por múltiplos atores;
- capaz de preservar histórico completo;
- capaz de distinguir acontecimentos históricos de resultados considerados válidos para consolidação;
- suficientemente padronizado para permitir acompanhamento operacional e gerencial;
- suficientemente flexível para lidar com reexecuções, variações de formulários e diferenças entre tipos de validação.

---

## 3. Premissa arquitetural

A aplicação não deve partir da premissa de que é necessário construir um workflow engine genérico e altamente configurável.

Durante a exploração do MVP, observou-se que os processos são predominantemente padronizados e que a maior necessidade está em:

- representar atividades como unidades de trabalho;
- controlar dependências;
- atribuir responsabilidades;
- registrar resultados;
- permitir reexecução parcial;
- preservar histórico;
- reutilizar blocos de processo;
- coletar dados por formulários configuráveis;
- controlar artefatos produzidos e consumidos;
- permitir acompanhamento por Kanban e visões macro;
- suportar regras de governança e aprovação.

A arquitetura deve evitar complexidade configurável que não tenha uma necessidade concreta no domínio.

---

## 4. Problemas que a arquitetura precisa resolver

### 4.1 Reexecução parcial de um processo

Uma atividade pode falhar depois que atividades anteriores foram concluídas.

Exemplo:

`1 → 2 → 3 → 4 → 5`

Se a atividade 5 apresentar um problema que exige repetir parte do estudo, o processo pode precisar executar novamente:

`1 → 2 → 3 → 4 → 5 → 3 → 4 → 5`

A arquitetura não deve exigir que o processo seja reiniciado nem deve apagar ou sobrescrever o que ocorreu anteriormente.

A nova execução deve ser representada como uma nova execução das atividades necessárias.

---

### 4.2 Preservação integral do histórico

O histórico precisa preservar tanto sucessos quanto falhas, inclusive atividades posteriormente consideradas inválidas para a consolidação.

Não é aceitável que uma reexecução substitua silenciosamente a execução anterior.

Exemplo:

- Execução #1 da atividade 3: concluída;
- Execução #1 da atividade 4: concluída;
- Execução #1 da atividade 5: falhou;
- Execução #2 da atividade 3: concluída;
- Execução #2 da atividade 4: concluída;
- Execução #2 da atividade 5: aprovada.

Ambas as execuções precisam continuar disponíveis para auditoria.

---

### 4.3 Separação entre histórico e evidência válida

O fato de uma execução ter ocorrido não significa que ela deva ser utilizada em um relatório de consolidação.

A arquitetura precisa permitir:

1. preservar tudo que ocorreu;
2. identificar quais execuções ou resultados são válidos;
3. selecionar explicitamente quais resultados serão utilizados em determinada consolidação.

Isso é necessário porque poderão existir:

- execuções com erro;
- execuções substituídas;
- resultados rejeitados;
- estudos complementares;
- revisões;
- diferentes rodadas do mesmo estudo.

O relatório histórico e o relatório de consolidação são, portanto, visões diferentes do mesmo conjunto de informações.

---

### 4.4 Dependência entre atividades

As atividades não formam apenas uma sequência linear.

Uma atividade pode depender de resultados produzidos por diversas atividades anteriores.

Exemplo:

- Grupo de Seleção de Amostras define as amostras;
- outra atividade define os laboratórios participantes;
- geração de códigos cegos precisa dos dois resultados;
- o Estatístico cria o template de coleta;
- o Grupo Gestor aprova o template;
- a execução laboratorial precisa do conjunto de códigos cegos e do template aprovado.

Portanto, uma simples propriedade `depends_on_activity` pode ser insuficiente.

A arquitetura precisa representar dependências entre atividades e os resultados produzidos por elas.

---

### 4.5 Atividades bloqueadas por ausência de pré-condições

Uma atividade pode existir no processo, mas ainda não estar apta para execução.

Exemplos:

- geração de códigos cegos aguardando laboratórios;
- exportação de template aguardando aprovação;
- execução laboratorial aguardando amostras e template;
- consolidação aguardando resultados válidos.

O sistema deve distinguir pelo menos entre:

- atividade ainda não disponível;
- atividade pronta para execução;
- atividade em execução;
- atividade bloqueada;
- atividade concluída;
- atividade falha;
- atividade cancelada.

O bloqueio deve ser explicável para o usuário.

---

### 4.6 Dependência de resultados, não apenas de atividades

Uma atividade pode consumir um resultado específico produzido por outra.

Exemplo:

`Selecionar Amostras → SampleSelection`

`Selecionar Laboratórios → LaboratorySelection`

`SampleSelection + LaboratorySelection → BlindCodeSet`

`Definir Data Template → DataTemplate`

`Aprovar Data Template → ApprovedDataTemplate`

`BlindCodeSet + ApprovedDataTemplate → Execução Laboratorial`

O modelo precisa permitir que uma atividade consuma somente resultados que estejam em estado adequado para consumo.

---

### 4.7 Reutilização de atividades semelhantes

Os três pipelines principais possuem estrutura amplamente semelhante.

As diferenças estão principalmente em:

- formulários;
- dados coletados;
- quantidade de amostras;
- quantidade de laboratórios;
- características específicas da execução.

Não deve haver três implementações completamente independentes do mesmo processo.

A arquitetura deve permitir definir atividades reutilizáveis e parametrizáveis.

---

### 4.8 Múltiplas rodadas de uma mesma atividade

Na validação, a preparação e a execução podem ocorrer em mais de uma rodada.

Exemplo:

Primeira rodada:

- 6 amostras;
- 4 laboratórios;
- execução preliminar;
- consolidação.

Segunda rodada:

- aproximadamente 40 amostras;
- maior número possível de laboratórios;
- nova execução;
- consolidação.

As duas rodadas possuem estrutura semelhante, mas são execuções distintas.

A arquitetura deve permitir:

`Activity → ActivityRun #1 → ActivityRun #2 → ...`

sem duplicar a definição estrutural da atividade.

---

### 4.9 Parametrização das execuções

Uma mesma atividade pode receber parâmetros diferentes por execução.

Exemplo:

- quantidade de amostras;
- conjunto de laboratórios;
- formulário utilizado;
- escopo;
- versão de template;
- regras específicas da rodada.

A parametrização não deve exigir uma nova tabela estrutural para cada variante.

---

### 4.10 Formulários configuráveis

Os formulários variam entre processos e atividades.

A arquitetura precisa permitir campos como:

- texto;
- inteiro;
- número decimal;
- booleano;
- seleção;
- data;
- arquivo;
- campos compostos, quando necessário.

Os campos devem permitir configuração de:

- obrigatoriedade;
- tipo;
- unidade;
- precisão;
- regras de validação;
- opções;
- dependências;
- versão do formulário.

---

### 4.11 Validação assistida por IA

Alguns formulários poderão utilizar agentes de IA para avaliar o conteúdo informado.

A IA não deve ser confundida com o motor de workflow.

A arquitetura deve permitir que uma submissão de formulário passe por:

1. validação estrutural;
2. validação determinística;
3. validação assistida por IA;
4. revisão ou decisão humana quando aplicável.

A decisão final deve continuar sendo governável e auditável.

A solução também precisa preservar o conteúdo analisado, a versão da avaliação e o resultado produzido pelo mecanismo de IA.

---

### 4.12 Atribuição de papéis durante o processo

Embora exista RBAC global, o processo possui papéis locais.

Exemplos:

- Proponente;
- Grupo Gestor;
- Estatístico;
- Laboratório Líder;
- Laboratório Participante;
- Grupo de Seleção de Amostras;
- Comitê Ad-hoc.

Uma pessoa pode receber ou deixar de possuir determinada responsabilidade dentro de uma instância de processo.

A arquitetura precisa representar atribuições locais sem substituir o RBAC global.

As atribuições devem possuir histórico.

---

### 4.13 Blindagem das amostras

Laboratórios não podem visualizar a identidade real das amostras durante a execução quando o processo exige cegamento.

A arquitetura precisa separar:

- identidade real da amostra;
- código cego;
- laboratório associado;
- informações que cada ator está autorizado a visualizar.

A geração de códigos cegos depende do conjunto de laboratórios participantes.

Uma alteração nos laboratórios pode exigir nova execução da atividade de geração ou atualização controlada dos códigos.

---

### 4.14 Versionamento de artefatos

Artefatos relevantes podem ser alterados ao longo do processo.

O Data Template é um exemplo.

O Estatístico pode produzir uma versão, o Grupo Gestor pode aprová-la e uma execução posterior deve utilizar exatamente aquela versão.

Uma alteração posterior não deve modificar silenciosamente o artefato já utilizado.

O modelo precisa suportar:

- versão;
- estado;
- aprovação;
- substituição;
- vínculo com as execuções que utilizaram aquela versão.

---

### 4.15 Uso de um mesmo artefato em múltiplas etapas

O Data Template pode ser apresentado em uma etapa para aprovação e posteriormente disponibilizado novamente na execução laboratorial.

Isso não significa necessariamente que existam duas definições de template.

É o mesmo artefato, ou uma versão específica dele, consumido por atividades diferentes.

A arquitetura deve suportar múltiplos consumidores do mesmo artefato.

---

### 4.16 Gates e aprovações formais

Algumas atividades não devem apenas ser concluídas; precisam ser aprovadas por um ator autorizado.

Exemplo:

- Estatístico conclui o template;
- Grupo Gestor revisa;
- Grupo Gestor aprova;
- somente depois a execução pode prosseguir.

Conclusão de atividade e aprovação de resultado são conceitos diferentes.

---

### 4.17 Acompanhamento operacional

Usuários internos precisam de uma visão de tarefas pendentes.

O sistema deve permitir uma representação Kanban ou equivalente com estados como:

- aguardando;
- disponível;
- em andamento;
- bloqueada;
- concluída;
- falha.

O usuário deve conseguir identificar:

- o que precisa fazer;
- por que está bloqueado;
- quais dependências faltam;
- qual processo e atividade originaram a tarefa.

---

### 4.18 Acompanhamento macro

Grupo Gestor e BraCVAM precisam de uma visão diferente da visão operacional.

Devem conseguir observar:

- fase atual;
- atividades concluídas;
- atividades pendentes;
- atividades bloqueadas;
- execuções adicionais;
- aprovações pendentes;
- problemas;
- andamento de laboratórios;
- progresso geral.

A visão macro não deve exigir que o usuário acompanhe cada tarefa individualmente.

---

### 4.19 Geração de relatórios diferentes a partir do mesmo histórico

O sistema deverá permitir pelo menos duas perspectivas:

#### Relatório histórico

Apresenta tudo que ocorreu, incluindo:

- erros;
- tentativas;
- reexecuções;
- rejeições;
- decisões;
- alterações;
- versões.

#### Relatório de consolidação

Apresenta somente os resultados selecionados como válidos para determinada consolidação.

A arquitetura não deve duplicar os dados para gerar esses documentos.

---

## 5. Objeções e decisões arquiteturais

### 5.1 Não construir um workflow engine genérico inicialmente

A necessidade de customização arbitrária ainda não foi demonstrada.

Um motor extremamente genérico aumentaria:

- complexidade;
- custo de desenvolvimento;
- superfície de configuração;
- dificuldade de testes;
- dificuldade de governança;
- risco de criar comportamentos difíceis de explicar.

A solução deve ser extensível, mas não precisa transformar todas as regras em configuração.

---

### 5.2 Não representar tudo como uma State Machine

Uma State Machine é adequada para estados e transições, mas não deve carregar sozinha:

- tarefas;
- dependências;
- artefatos;
- formulários;
- reexecuções;
- versões;
- consolidação.

O modelo deve utilizar State Machine como parte da solução.

---

### 5.3 Não apagar ou sobrescrever execuções anteriores

Reexecução não é rollback destrutivo.

Uma nova execução deve preservar a execução anterior.

---

### 5.4 Não duplicar processos estruturalmente iguais

Os três pipelines não devem possuir três conjuntos independentes de tabelas ou lógica apenas porque os formulários ou parâmetros variam.

A estrutura comum deve ser reutilizada.

---

### 5.5 Não acoplar a arquitetura a tecnologia específica

Este documento descreve comportamento e modelo conceitual.

Decisões sobre:

- linguagem;
- banco de dados;
- framework;
- mensageria;
- armazenamento;
- infraestrutura;
- mecanismos de IA;

devem ser tratadas separadamente.

---

## 6. Limitações conhecidas

### 6.1 O processo é regulado, mas nem toda regra é conhecida antecipadamente

A arquitetura deve permitir evolução, mas não deve presumir que todas as regras futuras precisam ser configuráveis desde o primeiro dia.

### 6.2 Nem toda repetição possui a mesma regra

Uma reexecução pode exigir:

- repetir somente algumas atividades;
- invalidar resultados anteriores;
- preservar resultados anteriores;
- criar uma nova rodada;
- criar uma execução complementar.

O modelo precisa suportar esses cenários sem impor uma única interpretação.

### 6.3 Dependências podem ser complexas

Nem toda dependência será uma relação simples entre duas atividades.

Pode haver dependência de:

- aprovação;
- versão de artefato;
- conjunto de participantes;
- conjunto de amostras;
- resultado válido;
- quantidade mínima de execuções.

### 6.4 IA não deve ser tratada como autoridade implícita

Resultados de IA precisam ser tratados como entradas ou avaliações do processo, com contexto e rastreabilidade próprios.

### 6.5 Regras de cegamento são requisitos de segurança e governança

Não basta esconder um campo na interface. A separação de informações deve existir também na camada de acesso aos dados e na geração das respostas do sistema.

---

## 7. Critérios de sucesso arquitetural

A arquitetura será considerada adequada se conseguir representar, sem alterações estruturais relevantes:

1. uma execução normal do processo;
2. uma falha em uma atividade seguida de reexecução parcial;
3. múltiplas rodadas de uma mesma atividade;
4. dependência entre resultados produzidos por atividades diferentes;
5. aprovação formal de um artefato;
6. reutilização de um artefato aprovado em atividades posteriores;
7. geração de códigos cegos dependente de amostras e laboratórios;
8. formulários diferentes utilizando o mesmo mecanismo;
9. validação determinística e assistida por IA;
10. atribuição de papéis durante o processo;
11. visão Kanban de tarefas;
12. visão macro do processo;
13. preservação integral do histórico;
14. seleção de resultados válidos para consolidação;
15. geração de relatórios históricos e consolidados a partir dos mesmos dados;
16. evolução dos templates sem alterar retroativamente processos já iniciados.

---

## 8. Princípio orientador

A arquitetura deve privilegiar **rastreabilidade, reutilização e explicabilidade** em vez de flexibilidade irrestrita.

O sistema deve ser capaz de responder, para qualquer decisão relevante:

- o que aconteceu;
- quando aconteceu;
- quem realizou;
- em qual processo;
- em qual atividade;
- em qual execução;
- com quais entradas;
- qual resultado foi produzido;
- qual versão do artefato foi utilizada;
- quais aprovações existiam;
- por que a atividade pôde ou não pôde avançar;
- se o resultado foi considerado válido para consolidação.


# Plano de Trabalho

## Fase II

### Desenvolvimento e Implantação da plataforma pi\*VMA

**Plataforma Inteligente de Validação de Métodos Alternativos**

**Julho de 2026**

> **Nota de conversão:** a fonte é o arquivo `_________FaseII_Plano de Trabalho_MetodosAlternativos_BraCVAM)_v2 - Copia.pdf`. Este Markdown preserva a redação, a terminologia, a grafia e a ordem lógica do PDF oficial. Observações editoriais e pontos a validar foram separados em `observacoes-e-pendencias.md`.

## Tabela de Glossário

| Sigla | Descrição |
|---|---|
| CONCEA | National Council for the Control of Animal Experimentaion |
| BraCVAM | Brazilian Centre for Validation of Alternative Methods - é uma iniciativa coordenada pela Fiocruz que atua no desenvolvimento, validação, divulgação e implementação de métodos alternativos ao uso de animais em pesquisa, ensino e testes laboratoriais. Centro Brasileiro para Validação de Métodos Alternativos |
| ReNaMA | National Network of Alternative Methods |
| Método Alternativo | Técnica desenvolvida para substituir ou reduzir o uso de animais em experimentos científicos |
| crCode | Identificador único atribuído a cada método submetido |
| Peer Review Committee | Comitê responsável pela revisão científica dos métodos |

## 1. Objetivo do Plano de Trabalho

O presente instrumento tem por objeto a formalização do Plano de Trabalho da Fase II do projeto “pi\*VMA – Plataforma Inteligente de Validação de Métodos Alternativos”, referente às atividades de desenvolvimento e implantação das funcionalidades especificadas no protótipo construído na Fase I do projeto. Esta nova fase contempla o desenvolvimento do módulo de submissão de novos métodos; do módulo de configuração dinâmica dos formulários; do módulo de ingestão de dados e resultados pelos laboratórios participantes; do módulo de validação ad hoc; e das páginas de monitoramento destinadas à Coordenação da BraCVAM, aos laboratórios, estatístico, aos especialistas, aos analistas e às demais partes interessadas. A plataforma atuará como um ambiente centralizado para a organização das submissões, a gestão dos dados experimentais, o acompanhamento das etapas de validação e a análise dos resultados com apoio de Inteligência Artificial. Nesse processo, a Coordenação da BraCVAM será responsável por definir os protocolos e configurar os formulários de ensaio; os laboratórios participantes realizarão os testes e registrarão os dados e resultados; e os analistas revisarão e consolidarão os resultados para gerar a validação final. A plataforma será construída para atender os pilares da rastreabilidade, padronização e eficiência na condução do processo de validação de métodos alternativos.

### Responsável pela Execução do Projeto

| Campo | Informação |
|---|---|
| Nome do órgão | FIOCRUZ- BraCVAM |
| Gestor do Projeto | Octavio Augusto França Presgrave |

## 2. Detalhes do Plano

A plataforma apoiará a execução e a avaliação dos métodos mediante a utilização de amostras codificadas e de critérios científicos e regulatórios previamente definidos pelo Grupo Gestor. Também organizará as atividades do Gerente do Estudo; a submissão e a análise inicial de novos métodos; a validação ad hoc; a configuração dinâmica dos formulários de ensaio; a gestão dos ensaios interlaboratoriais; a ingestão dos dados e resultados produzidos pelos laboratórios participantes; a revisão por pares; a governança dos dados; e a consolidação dos resultados pelos especialistas e analistas responsáveis por subsidiar e gerar a validação final.

Nos ensaios interlaboratoriais, a plataforma permitirá a gestão independente do laboratório desenvolvedor do método, possibilitando a verificação de sua transferibilidade e reprodutibilidade em diferentes laboratórios. Para preservar a independência dos resultados, o sistema deverá impedir a troca de informações entre os laboratórios participantes, realizar o embaralhamento da codificação dos insumos e assegurar a segurança, a confidencialidade e o acesso individualizado aos dados de cada laboratório. Deve também gerir o processo de eventuais problemas e ou perdas das amostras.

A plataforma também disponibilizará funcionalidades para apoiar o Peer Review Committee, incluindo a designação de revisores, a distribuição automática dos materiais para avaliação, o controle de prazos, a revisão cega, quando aplicável, o registro de pareceres e a consolidação das recomendações.

Adicionalmente, serão desenvolvidos mecanismos automatizados, apoiados por Inteligência Artificial Generativa, para verificar a completude das submissões, identificar inconsistências formais e auxiliar na análise de conformidade das propostas em relação aos critérios estabelecidos pelo Grupo Gestor.

A plataforma contará, ainda, com notificações assíncronas para informar proponentes, avaliadores, gestores, laboratórios, especialistas e analistas sobre solicitações, pendências, prazos, devolutivas e avanços no processo. Um módulo de monitoramento apresentará o status atualizado das etapas concluídas, em andamento e futuras, garantindo transparência e rastreabilidade integral. Ao final do processo, a plataforma apoiará os analistas na revisão, agregação e consolidação dos dados, pareceres e resultados, bem como na elaboração do relatório final da validação.

A plataforma será estruturada em seis módulos integrados, que abrangem todo o ciclo de validação:

1. Módulo de Gestão de Usuários
2. Módulo de Submissão de Métodos
3. Módulo Configurador da Base de Conhecimento da IA
4. Módulo de Aprovação e Gestão do Processo
5. Módulo de Ensaios Interlaboratoriais
6. Módulo de Avaliação Ad Hoc e Análise Estatística

## 3. Requisitos funcionais por módulo

Os requisitos funcionais estão organizados por módulo e numerados sequencialmente de RF001 a RF062.

### 3.1. Módulo de Gestão de Usuários

Responsável pelo cadastro, autenticação e gerenciamento dos usuários da plataforma. O módulo permitirá a definição de diferentes perfis e níveis de acesso, considerando as atribuições do Proponente, Grupo Gestor, Gerente do Estudo, Laboratório Participante, Avaliador Ad Hoc, Revisor, Especialista, Analista Estatístico e Administrador.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF001 | Cadastro e autenticação | Permitir o cadastro e a autenticação dos usuários da plataforma. |
| RF002 | Gestão de perfis de acesso | Permitir a criação e a administração de perfis com diferentes permissões, atribuições e responsabilidades. |
| RF003 | Vinculação institucional | Permitir a vinculação dos usuários às instituições e aos laboratórios participantes. |
| RF004 | Controle de acesso | Controlar o acesso às funcionalidades e aos dados de acordo com o perfil, a instituição e a participação do usuário no processo. |
| RF005 | Designação de participantes | Permitir a designação de gestores, laboratórios, avaliadores ad hoc, revisores, especialistas e analistas para cada processo de validação. |
| RF006 | Declaração de conflito de interesse | Permitir que os participantes registrem a existência ou a ausência de conflito de interesse. |

### 3.2. Módulo de Submissão de Métodos

Responsável pelo recebimento estruturado das propostas de novos métodos alternativos. Cada submissão será individualizada por um código exclusivo, denominado crCode, utilizado para identificar o método, organizar o fluxo de trabalho, registrar os eventos e assegurar a rastreabilidade do processo.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF007 | Submissão de método alternativo | Permitir o cadastro estruturado de novos métodos, com o preenchimento das informações técnicas e científicas requeridas. |
| RF008 | Anexação de documentos | Permitir a inclusão de protocolos, evidências, resultados preliminares, referências e demais arquivos relacionados ao método. |
| RF009 | Edição da submissão | Permitir ao proponente editar as informações e os documentos enquanto a submissão estiver em elaboração, ajuste ou complementação. |
| RF010 | Versionamento da submissão | Manter o histórico das versões, registrando alterações, datas e respectivos responsáveis. |
| RF011 | Notificação Assíncrona com retornos da IA e validação | Gerar notificações assíncrona com retornos da IA e validação . |
| RF012 | Gestão eletrônica de documentos | Permitir o armazenamento seguro, a classificação, a consulta e o controle de versões dos documentos. |
| RF013 | Verificação por IA | Verificar a submissão através de IA com base na base de conhecimento |
| RF014 | Envio para análise | Permitir que o proponente encaminhe formalmente o método para avaliação do Grupo Gestor. |

### 3.3. Módulo Configurador da Base de Conhecimento da IA

Responsável pela criação, atualização e governança da base de conhecimento utilizada pelos recursos de Inteligência Artificial da plataforma. O módulo permitirá que usuários autorizados configurem critérios científicos, técnicos e regulatórios para apoiar a análise das submissões, sem substituir a decisão dos especialistas.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF015 | Gestão da base de conhecimento | Permitir o cadastro, a atualização e a organização dos conhecimentos utilizados pela IA. |
| RF016 | Gestão da taxonomia de validação | Permitir a criação e a manutenção de categorias e critérios científicos, técnicos e regulatórios. |
| RF017 | Configuração de critérios de análise | Permitir ao Grupo Gestor definir critérios de completude, conformidade e alinhamento das submissões. |
| RF018 | Vinculação de fontes documentais | Permitir a inclusão de normas, regulamentos, protocolos, artigos e documentos técnicos na base de conhecimento. |
| RF019 | Versionamento da base de conhecimento | Manter o histórico das alterações realizadas nos critérios, documentos e configurações da IA. |
| RF020 | Checklist automatizado por IA | Avaliar a completude da submissão, identificando campos, informações ou documentos ausentes. |
| RF021 | Identificação de inconsistências | Utilizar IA Generativa para apontar inconsistências formais e possíveis divergências em relação aos critérios cadastrados. |
| RF022 | Registro das análises da IA | Armazenar as análises e recomendações produzidas pela IA, indicando a base e os critérios utilizados. |
| RF023 | Validação humana das recomendações | Permitir que especialistas revisem, aceitem, ajustem ou rejeitem as recomendações geradas pela IA. |

### 3.4. Módulo de Aprovação e Gestão do Processo

Responsável pela coordenação do fluxo de validação, desde o recebimento da submissão até a deliberação final. O módulo apoiará as atividades do Grupo Gestor e do Gerente do Estudo, incluindo definição das etapas, distribuição das responsabilidades, controle de prazos e registro das decisões.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF024 | Configuração do fluxo de validação | Permitir a definição das etapas, atividades, responsáveis e critérios do processo. |
| RF025 | Análise inicial da submissão | Permitir ao Grupo Gestor verificar a admissibilidade e a conformidade inicial do método. |
| RF026 | Aprovação, devolução ou rejeição | Permitir aprovar a continuidade da submissão, solicitar ajustes ou registrar sua rejeição. |
| RF027 | Registro de deliberações | Registrar decisões, justificativas, recomendações e critérios adotados pelo Grupo Gestor. |
| RF028 | Gestão de reuniões e atas | Permitir o registro de reuniões, participantes, pautas, deliberações e respectivos documentos. |
| RF029 | Controle de prazos | Permitir a definição e o acompanhamento dos prazos de cada etapa e de cada participante. |
| RF030 | Visualização do fluxo | Apresentar as etapas concluídas, em andamento, pendentes e futuras do processo. |
| RF031 | Painel de monitoramento | Disponibilizar indicadores sobre submissões, avaliações, ensaios, pendências e prazos. |
| RF032 | Comentários e anotações | Permitir o registro de comentários, orientações e interações entre os usuários autorizados. |
| RF033 | Notificações assíncronas | Enviar notificações sobre solicitações, pendências, prazos, devolutivas e mudanças de status. |
| RF034 | Logs e auditoria | Registrar usuários, datas, alterações, decisões e demais eventos realizados na plataforma. |

### 3.5. Módulo de Ensaios Interlaboratoriais

Responsável pelo planejamento, execução e monitoramento dos ensaios realizados pelos laboratórios participantes. O módulo permitirá avaliar a transferibilidade e a reprodutibilidade do método de forma independente do laboratório desenvolvedor. A plataforma utilizará amostras codificadas e mecanismos de embaralhamento para preservar o cegamento. Cada laboratório acessará exclusivamente seus próprios dados durante a execução dos ensaios, impedindo a troca indevida de informações e assegurando confidencialidade e independência dos resultados.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF035 | Configuração do ensaio | Permitir ao Grupo Gestor ou ao Gerente do Estudo definir o protocolo, as etapas, os laboratórios e os critérios do ensaio. |
| RF036 | Configuração dinâmica de formulários | Permitir a criação de formulários específicos para o registro da execução e dos resultados de cada método. |
| RF037 | Gestão dos laboratórios | Permitir selecionar, cadastrar e vincular os laboratórios participantes ao ensaio. |
| RF038 | Codificação de amostras | Permitir o cadastro, a codificação e o embaralhamento das amostras e dos insumos. |
| RF039 | Registro do despacho | Registrar o envio das amostras aos laboratórios, incluindo datas, códigos e informações de acompanhamento. |
| RF040 | Check-in das amostras | Permitir que o laboratório registre o recebimento e as condições das amostras. |
| RF041 | Registro da execução | Permitir que os laboratórios registrem as etapas de execução do protocolo experimental. |
| RF042 | Ingestão de dados e resultados | Permitir o preenchimento dos formulários e o envio dos dados experimentais. |
| RF043 | Anexação de dados brutos | Permitir a anexação de planilhas, imagens, laudos e outros arquivos produzidos durante o ensaio. |
| RF044 | Controle de acesso por laboratório | Garantir que cada laboratório visualize apenas seus dados durante as etapas restritas do ensaio. |
| RF045 | Submissão dos resultados | Permitir que o laboratório encaminhe os dados completos ao Gerente do Estudo e à Coordenação. |
| RF046 | Monitoramento interlaboratorial | Permitir o acompanhamento do recebimento das amostras, da execução, dos prazos e da submissão dos resultados. |
| RF047 | Verificação da reprodutibilidade | Apoiar a comparação dos resultados obtidos pelos diferentes laboratórios. |

### 3.6. Módulo de Avaliação Ad Hoc e Análise Estatística

Responsável pela avaliação especializada dos métodos e pela análise e consolidação dos resultados experimentais. O módulo oferecerá recursos para o Peer Review Committee, para os avaliadores ad hoc e para os analistas estatísticos responsáveis por revisar e consolidar os dados que subsidiarão a validação final.

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF048 | Designação de avaliadores ad hoc | Permitir a seleção e a designação de especialistas para avaliar cada método. |
| RF049 | Distribuição dos materiais | Distribuir automaticamente aos avaliadores os documentos e materiais necessários à avaliação. |
| RF050 | Revisão cega | Preservar a identidade dos participantes quando o processo de avaliação exigir cegamento. |
| RF051 | Registro de pareceres | Permitir o preenchimento, a edição e a submissão dos pareceres dos avaliadores. |
| RF052 | Anexação de arquivos | Permitir que os avaliadores anexem documentos, evidências e materiais complementares aos pareceres. |
| RF053 | Avaliação com apoio de IA | Oferecer suporte opcional de IA para a verificação de completude e conformidade, sem substituir o parecer do especialista. |
| RF054 | Consolidação das recomendações | Permitir a organização e a consolidação dos pareceres e das recomendações dos avaliadores. |

#### Continuação - requisitos do módulo

| Código | Requisito funcional | Descrição |
|---|---|---|
| RF055 | Ingestão dos dados para análise | Permitir ao analista importar e organizar os resultados experimentais dos laboratórios. |
| RF056 | Tratamento estatístico | Permitir a aplicação de métodos estatísticos definidos para avaliar desempenho, variabilidade e reprodutibilidade. |
| RF057 | Comparação interlaboratorial | Permitir a comparação dos resultados entre os laboratórios participantes. |
| RF058 | Indicadores analíticos | Gerar indicadores e representações visuais de conformidade, desempenho e reprodutibilidade. |
| RF059 | Consolidação dos resultados | Permitir aos analistas consolidar os dados experimentais, as análises estatísticas, os pareceres e as recomendações. |
| RF060 | Validação final | Permitir o registro da conclusão do processo de validação, de sua fundamentação e da decisão do Grupo Gestor. |
| RF061 | Geração do relatório final | Gerar o relatório consolidado com dados, análises, pareceres, recomendações, deliberações e resultados do processo. |
| RF062 | Exportação de dados e relatórios | Permitir a exportação dos dados e relatórios em formatos PDF e planilha eletrônica. |

## 4. Planejamento de Sprints por Módulo

O projeto será conduzido com base em conceitos de gestão de projetos, utilizando Scrum e Corrente Crítica para otimizar a operacionalização e a gestão da equipe. Outra estratégia metodológica, são as reuniões semanais com o grupo gestor realizadas para validar rapidamente os artefatos entregues e discutir eventuais ajustes ou mudanças

| Nº | Módulo | Quantidade de sprints |
|---:|---|---:|
| 1 | Módulo de Gestão de Usuários | 2 sprints |
| 2 | Módulo de Submissão de Métodos | 4 sprints |
| 3 | Módulo Configurador da Base de Conhecimento da IA | 3 sprints |
| 4 | Módulo de Aprovação e Gestão do Processo | 4 sprints |
| 5 | Módulo de Ensaios Interlaboratoriais | 3 sprints |
| 6 | Módulo de Avaliação Ad Hoc e Análise Estatística | 4 sprints |
|  | **Total estimado** | **20 sprints** |

\*Cada sprint será planejada e executada em uma semana

## 5. Perfis e atividades da equipe do projeto

| Perfil | Atividades |
|---|---|
| Pesquisador Sênior | Especificação do projeto e acompanhamento técnico da equipe no desenvolvimento do módulo de submissão de novos métodos e de análise dos testes realizados pelos laboratórios para validação de métodos alternativos. |
| Pesquisador Sênior | Elaboração de casos e cenários de teste de software com base no marco regulatório e nas especificações dos usuários; validação do módulo de submissão e análise dos testes realizados pelos laboratórios; e planejamento da integração do IA-OIACTEST à plataforma pi\*VMA. |
| Pesquisador III — Desenvolvedor Sênior | Liderança técnica da equipe; elicitação e priorização de requisitos com base no método MoSCoW; elaboração e acompanhamento da matriz de rastreabilidade; e verificação da completude dos requisitos e das funcionalidades do software pi\*VMA. |
| Pesquisador III — Desenvolvedor Sênior | Desenvolvimento da camada de back-end integrada à Inteligência Artificial; implementação do componente de comunicação assíncrona; e implantação do software pi\*VMA na AWS. |
| Pesquisador II — Desenvolvedor Front-end | Desenvolvimento da camada de front-end do módulo de submissão de novos métodos e de análise dos testes realizados pelos laboratórios. |
| Pesquisador Júnior — Apoio ao Desenvolvimento | Elaboração da identidade visual, da marca e dos padrões de estética, experiência do usuário e usabilidade do projeto. |
| Pesquisador Júnior — Apoio ao Desenvolvimento | Desenvolvimento da camada de front-end do módulo de configuração da plataforma pi\*VMA. |

## 6. Cronograma do Projeto

**Quadro 1: Cronograma geral de execução do projeto para um período de 8 meses.**

| Atividade (Trimestre) | 1M | 2M | 3M | 4M | 5M | 6M | 7M | 8M |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Módulo de Gestão de Usuários | X |  |  |  |  |  |  |  |
| Módulo de Submissão de Métodos | X | X |  |  |  |  |  |  |
| Módulo Configurador da Base de Conhecimento da IA |  |  | X |  |  |  |  |  |
| Implantação e Treinamento I |  |  |  | X | X | X | X | X |
| Módulo de Aprovação e Gestão do Processo |  |  |  | X |  |  |  |  |
| Módulo de Ensaios Interlaboratoriais |  |  |  | X | X |  |  |  |
| Implantação e Treinamento II |  |  |  |  |  | X | X | X |
| Módulo de Avaliação Ad Hoc e Análise Estatística |  |  |  |  |  | X |  |  |
| Implantação e Treinamento III |  |  |  |  |  |  | X | X |
| Divulgação do projeto, Artigo Científico e Registro do Software |  |  |  | X |  |  |  | X |

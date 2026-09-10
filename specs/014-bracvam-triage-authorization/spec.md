# Feature Specification: Semântica BraCVAM e autorização da triagem

**Feature Branch**: `014-bracvam-triage-authorization`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Spec 014 — Semântica BraCVAM, autorização da triagem e remoção do pipeline legado (Spec 010). O código e a Spec 013 confundem 'BraCVAM' com 'Grupo Gestor' — são entidades distintas. Quem submete é o proponente; quem vê, avalia e faz a triagem é o BraCVAM + a Administração. A IA produz a pré-avaliação; a decisão é humana. Criar perfil de acesso 'bracvam' distinto; travar as ações de triagem à permissão BraCVAM; remover a esteira de avaliação legada da Spec 010; preservar por execução o conteúdo avaliado pela IA; cobrir a observabilidade da pré-avaliação."

## Contexto e Motivação

A Spec 013 entregou a avaliação configurável por IA na submissão e triagem. Durante a
revisão, três problemas ficaram evidentes:

1. **Confusão de entidades.** O texto da Spec 013 e o código tratam "BraCVAM" e
   "Grupo Gestor" como o mesmo papel. Não são: o **BraCVAM** é o corpo que coordena a
   submissão e conduz a triagem de um método candidato; o **Grupo Gestor** é a gestão
   de um estudo de validação já em andamento — um papel posterior no ciclo de vida.
   Hoje a leitura da pré-avaliação e o feedback por critério dependem de o usuário ser
   "gestor do processo" (`group_manager`), o que é semanticamente errado e, na prática,
   força contornos nos seeds.

2. **Triagem sem controle de acesso.** As ações centrais da triagem — registrar
   parecer campo a campo e emitir a decisão regulatória — não têm nenhuma verificação
   de perfil hoje: qualquer usuário autenticado e sem conflito de interesse pode
   executá-las.

3. **Duas esteiras de avaliação coexistindo.** A esteira mock da Spec 010 (parecer
   automatizado por campo, com veredito fixo) só é acionada quando o formulário não
   tem avaliações por IA associadas. Ela duplica o propósito da pré-avaliação da Spec
   013, gera um segundo formato de relatório e um segundo formato de log, e mantém um
   endpoint de disparo manual sem função no fluxo real.

Some-se a isso que o "conteúdo avaliado" apresentado ao triador é hoje reconstruído a
partir do formulário no momento da consulta — se a configuração de avaliação mudar
depois, a reconstrução deixa de refletir o que a IA de fato analisou.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Triagem restrita ao BraCVAM e à Administração (Priority: P1)

Como membro do **BraCVAM** (ou da **Administração**), quero ser o único papel capaz de
conduzir a triagem de uma submissão — consultar a pré-avaliação por IA, registrar
concordância/discordância por critério e emitir a decisão regulatória — para que a
avaliação de mérito de um método candidato fique sob a autoridade institucional
correta e não seja acessível a proponentes nem a papéis de gestão de estudos.

**Why this priority**: é a correção de segurança e de modelo de domínio que motiva a
feature; sem ela as ações de triagem continuam abertas a qualquer usuário e a
semântica "BraCVAM = Grupo Gestor" permanece.

**Independent Test**: com o perfil BraCVAM criado, autenticar como usuário BraCVAM e
percorrer a triagem completa de uma submissão (ver pré-avaliação, registrar feedback
por critério, decidir); depois autenticar como usuário de perfil "Grupo Gestor" e como
proponente de outro processo e confirmar que cada ação de triagem é recusada.

**Acceptance Scenarios**:

1. **Given** um usuário com o perfil **BraCVAM**, **When** ele abre a tarefa de
   triagem de uma submissão, **Then** consegue ver o painel da pré-avaliação por IA,
   registrar feedback por critério e emitir a decisão de triagem.
2. **Given** um usuário com o perfil **Administrador** (Administração), **When** ele
   executa qualquer ação de triagem, **Then** o sistema permite, com os mesmos
   direitos do BraCVAM.
3. **Given** um usuário cujo único perfil é **Grupo Gestor**, **When** ele tenta
   registrar parecer de campo, emitir decisão de triagem, ler a pré-avaliação ou
   registrar feedback por critério, **Then** o sistema recusa a ação por falta de
   autorização.
4. **Given** o **proponente** de um processo, **When** ele consulta a pré-avaliação
   **do seu próprio** processo, **Then** o sistema permite (acompanhamento do
   resultado); **When** ele tenta consultar a de outro processo ou registrar feedback
   de triagem, **Then** o sistema recusa.
5. **Given** um usuário com o perfil BraCVAM **mas com conflito de interesse vigente**
   no processo, **When** ele tenta registrar feedback ou decisão de triagem, **Then**
   o sistema bloqueia a ação (a guarda de conflito de interesse continua valendo e tem
   precedência).
6. **Given** o perfil **BraCVAM** recém-criado, **When** um administrador de RBAC lista
   os perfis, **Then** "BraCVAM" aparece como perfil distinto de "Grupo Gestor" e de
   "Revisor", com sua própria permissão de triagem.

---

### User Story 2 - Uma única esteira de avaliação por IA (Priority: P2)

Como responsável pela plataforma, quero que exista **apenas** a pré-avaliação
configurável da Spec 013 — sem a esteira mock da Spec 010 rodando em paralelo — para
que haja um só formato de relatório, um só formato de log e nenhum caminho de código
morto acionável.

**Why this priority**: reduz superfície de manutenção e ambiguidade; depende
conceitualmente da P1 estar decidida, mas é independente para testar e entregar.

**Independent Test**: submeter um formulário **sem** avaliações por IA associadas e
confirmar que o processo avança para a triagem com um relatório de pré-avaliação
vazio, sem nenhum "parecer técnico automatizado" legado e sem erro; confirmar que o
endpoint de disparo manual da avaliação legada não existe mais.

**Acceptance Scenarios**:

1. **Given** um formulário **sem** nenhuma avaliação por IA associada, **When** o
   proponente o submete, **Then** o processo avança direto para a triagem com um
   relatório de pré-avaliação **vazio** (contagem zero, sem pontos de atenção) e sem
   erro — comportamento idêntico ao já especificado na Spec 013 (FR-027), agora sem
   passar por nenhuma esteira mock.
2. **Given** um formulário **com** avaliações por IA associadas, **When** o proponente
   o submete, **Then** o fluxo assíncrono da Spec 013 (status "pré-avaliação em
   andamento", processamento em segundo plano, roteamento fixo) ocorre sem alteração.
3. **Given** a plataforma após esta entrega, **When** um cliente chama o antigo
   endpoint de disparo manual da avaliação legada, **Then** o endpoint não existe (404).
4. **Given** a resposta da submissão de um formulário, **When** um cliente a inspeciona,
   **Then** ela não contém mais o campo do parecer automatizado legado; apresenta
   apenas o identificador da pré-avaliação (quando houver) e o status.
5. **Given** um processo **antigo** cuja submissão já registrou um parecer legado antes
   desta entrega, **When** um triador abre a triagem, **Then** a tarefa abre
   normalmente; o histórico/artefato antigo é preservado para auditoria, mas nenhum
   processamento legado novo ocorre.

---

### User Story 3 - Registro fiel do que a IA avaliou (Priority: P3)

Como triador do BraCVAM e como auditor, quero que o **conteúdo exato** que alimentou
cada execução de pré-avaliação fique preservado com a execução, para poder reconstruir
a análise mesmo que a configuração da avaliação ou a associação ao campo mude depois.

**Why this priority**: fecha uma lacuna de auditabilidade (Princípio V); é uma melhoria
de fidelidade sobre um recurso já entregue na Spec 013, não um bloqueio.

**Independent Test**: executar uma pré-avaliação; alterar depois a associação de
avaliação do template (remover o campo ou trocar a definição); reabrir a pré-avaliação
e confirmar que o "conteúdo avaliado" mostrado é o do momento da execução, não o
estado atual.

**Acceptance Scenarios**:

1. **Given** uma execução de pré-avaliação concluída, **When** o triador consulta o
   painel da IA, **Then** vê o conteúdo avaliado (campos cobertos, rótulo e valor
   submetido) exatamente como estava no momento da execução.
2. **Given** uma execução de pré-avaliação concluída, **When** a associação de
   avaliação do template é alterada ou o campo é removido, **Then** a consulta à
   pré-avaliação **daquela execução** continua mostrando o conteúdo original.
3. **Given** uma execução de pré-avaliação com um alvo de formulário inteiro,
   **When** o triador consulta o conteúdo avaliado, **Then** vê todos os valores
   submetidos que alimentaram a IA.

---

### User Story 4 - Observabilidade da pré-avaliação (Priority: P4)

Como administrador ou auditor, quero acompanhar e reconstruir cada execução de
pré-avaliação como um agrupamento coerente de etapas, para ter rastreabilidade
operacional do processamento por IA.

**Why this priority**: a Spec 013 já implementou o agrupamento; falta a cobertura de
teste de regressão que o garante após a remoção do formato legado.

**Independent Test**: disparar uma execução de pré-avaliação e confirmar que suas
etapas de avaliação de critério aparecem agrupadas pelo identificador de correlação da
execução, com custo e provedor/modelo por camada.

**Acceptance Scenarios**:

1. **Given** uma execução de pré-avaliação, **When** um administrador consulta a
   observabilidade de IA, **Then** vê as etapas da execução agrupadas por um único
   identificador de correlação, com nome do fluxo, provedor, modelo por camada e custo
   real.
2. **Given** o formato de log da esteira legada removido, **When** a observabilidade é
   consultada, **Then** apenas o formato da pré-avaliação atual é apresentado, sem
   entradas órfãs do formato antigo.

---

### Edge Cases

- **Usuário BraCVAM + conflito de interesse**: a permissão concede acesso, mas a
  guarda de conflito de interesse vigente tem precedência e bloqueia feedback e
  decisão de triagem (cenário 1.5).
- **Formulário sem avaliações + esteira removida**: submissão vai à triagem com
  relatório vazio, sem erro (cenário 2.1).
- **Processo pré-migração com parecer legado**: a triagem abre; o artefato antigo é
  histórico imutável; nenhuma reexecução legada (cenário 2.5).
- **Downgrade da migração de RBAC**: reverter a criação do perfil BraCVAM e da
  permissão de triagem deve deixar o banco consistente (sem perfis/permissões órfãos,
  sem atribuições penduradas).
- **Downgrade da migração do snapshot de conteúdo**: reverter a coluna/tabela de
  snapshot não pode apagar execuções de pré-avaliação existentes.
- **Usuário sem nenhum perfil**: recusado em todas as ações de triagem.
- **Demo de observabilidade de IA**: o módulo `demos/ai-pipeline/` hoje dispara a
  esteira legada por um botão; com a esteira removida, ele passa a **observar**
  pré-avaliações originadas na demo de submissão, sem disparo próprio.

## Requirements *(mandatory)*

### Functional Requirements

#### Perfil e autorização

- **FR-001**: O sistema MUST oferecer um perfil de acesso institucional **"BraCVAM"**,
  distinto dos perfis "Grupo Gestor" e "Revisor", identificável de forma estável
  (chave de sistema própria).
- **FR-002**: O sistema MUST associar ao perfil BraCVAM uma **permissão de triagem**
  que autoriza: registrar parecer de campo, emitir decisão de triagem, consultar a
  pré-avaliação por IA de qualquer processo e registrar feedback por critério.
- **FR-003**: O sistema MUST conceder a mesma permissão de triagem ao perfil
  **Administrador** (Administração), com direitos equivalentes aos do BraCVAM para as
  ações de triagem.
- **FR-004**: O sistema MUST NOT conceder a permissão de triagem ao perfil "Grupo
  Gestor" nem a nenhum outro perfil por padrão; a atribuição a outros perfis é
  possível apenas pela gestão de RBAC.
- **FR-005**: O sistema MUST recusar, com erro de autorização, qualquer tentativa de
  registrar parecer de campo ou emitir decisão de triagem feita por usuário sem a
  permissão de triagem.
- **FR-006**: O sistema MUST recusar a consulta à pré-avaliação por IA e o registro de
  feedback por critério para usuários sem a permissão de triagem, **exceto** o
  proponente ativo do próprio processo, que MUST continuar podendo **consultar** a
  pré-avaliação do seu processo (não registrar feedback).
- **FR-007**: A guarda de **conflito de interesse** vigente MUST manter precedência
  sobre a permissão de triagem: um usuário autorizado mas com conflito no processo
  continua bloqueado para feedback e decisão de triagem.
- **FR-008**: A verificação da permissão de triagem MUST ser reavaliada no banco a
  cada requisição (sem cache no token), consistente com o Princípio VI.
- **FR-009**: A introdução do perfil e da permissão MUST ser feita por migração
  reversível: o upgrade cria o perfil, a permissão e o vínculo; o downgrade os remove
  sem deixar registros órfãos.
- **FR-010**: A carga de dados de demonstração MUST atribuir o perfil **BraCVAM** à
  conta de triagem semeada e MUST remover o contorno anterior que designava essa conta
  como "gestor do processo" apenas para viabilizar a demo.

#### Remoção da esteira legada (Spec 010)

- **FR-011**: O sistema MUST manter **uma única** forma de avaliação automatizada de
  submissão: a pré-avaliação configurável por IA da Spec 013.
- **FR-012**: O sistema MUST NOT executar nenhuma esteira de parecer automatizado por
  campo com veredito fixo ao submeter um formulário.
- **FR-013**: Um formulário **sem** avaliações por IA associadas MUST avançar direto
  para a triagem com um relatório de pré-avaliação vazio, sem erro e sem acionar
  qualquer processamento automatizado (reafirma FR-027 da Spec 013, agora sem
  fallback).
- **FR-014**: O sistema MUST NOT expor o endpoint de disparo manual da avaliação
  legada; uma chamada a ele MUST resultar em "não encontrado".
- **FR-015**: A resposta de conclusão da submissão MUST NOT conter o campo do parecer
  automatizado legado; MUST manter apenas os dados da pré-avaliação da Spec 013
  (identificador e status quando houver).
- **FR-016**: Artefatos e eventos de auditoria gerados pela esteira legada **antes**
  desta entrega MUST ser preservados (histórico imutável); a triagem de processos
  antigos MUST continuar acessível.
- **FR-017**: O formato de log específico da esteira legada MUST ser descontinuado; a
  observabilidade MUST apresentar apenas o formato da pré-avaliação atual.
- **FR-018**: O módulo de demonstração de observabilidade de IA MUST ser ajustado para
  **observar** execuções de pré-avaliação originadas na demonstração de submissão, sem
  disparar processamento por conta própria; a demonstração de submissão MUST perder o
  ramo que tratava o parecer legado.
- **FR-019**: A Spec 013 MUST ser atualizada para registrar que o débito do "motor de
  pipeline único" (FR-022) e o item L1 do `/speckit-analyze` estão fechados.

#### Registro fiel do conteúdo avaliado

- **FR-020**: No momento em que uma execução de pré-avaliação processa o conteúdo, o
  sistema MUST **capturar e persistir** com a execução o conteúdo efetivamente enviado
  à IA (campos cobertos, rótulo e valor), de forma imutável.
- **FR-021**: A consulta à pré-avaliação MUST apresentar o **conteúdo capturado na
  execução**, não uma reconstrução a partir do estado atual do formulário ou da
  associação.
- **FR-022**: A alteração ou remoção posterior da associação de avaliação, da
  definição/versão da avaliação ou de um campo do template MUST NOT alterar o conteúdo
  avaliado exibido para execuções já concluídas.
- **FR-023**: A persistência do snapshot MUST ser feita por migração reversível cujo
  downgrade não apague execuções de pré-avaliação existentes.
- **FR-024**: Para execuções concluídas **antes** desta entrega (sem snapshot), a
  consulta MUST degradar de forma graciosa para a reconstrução atual, sem erro.

#### Observabilidade

- **FR-025**: O sistema MUST agrupar as etapas de uma execução de pré-avaliação por um
  único identificador de correlação, apresentando nome do fluxo, provedor, modelo por
  camada e custo real por execução.
- **FR-026**: O comportamento de agrupamento MUST ter cobertura de teste de regressão
  que exercite uma execução real de pré-avaliação (com provedor determinístico) e
  verifique o agrupamento.

### Key Entities *(include if feature involves data)*

- **Perfil de Acesso "BraCVAM"**: papel institucional que representa a equipe do
  BraCVAM responsável por coordenar submissões e conduzir a triagem. Distinto de
  "Grupo Gestor" (gestão de estudo de validação) e "Revisor". Possui a permissão de
  triagem.
- **Permissão de Triagem**: autorização que habilita as ações de triagem (parecer de
  campo, decisão, consulta e feedback da pré-avaliação por IA). Detida pelos perfis
  BraCVAM e Administrador.
- **Snapshot de Conteúdo Avaliado**: registro imutável, vinculado a uma execução de
  pré-avaliação, do conteúdo do formulário que alimentou a IA naquela execução (lista
  de campos com rótulo e valor). Capturado no processamento; nunca atualizado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das ações de triagem (registrar parecer de campo, emitir decisão,
  consultar pré-avaliação, registrar feedback por critério) são recusadas para
  usuários sem a permissão de triagem, com a única exceção do proponente ativo
  consultando a pré-avaliação do próprio processo.
- **SC-002**: O perfil "Grupo Gestor" não consegue executar nenhuma ação de triagem em
  nenhum processo.
- **SC-003**: Um usuário com a permissão de triagem e conflito de interesse vigente
  continua bloqueado para feedback e decisão em 100% das tentativas.
- **SC-004**: Após a entrega, existe **zero** caminho de código que execute a esteira
  de parecer automatizado por campo, e **zero** endpoint de disparo manual dessa
  esteira.
- **SC-005**: Uma submissão de formulário sem avaliações por IA associadas chega à
  triagem em um único passo, com relatório de pré-avaliação vazio e sem erro, em 100%
  dos casos.
- **SC-006**: Para 100% das execuções de pré-avaliação concluídas **após** a entrega, o
  conteúdo avaliado é recuperável idêntico ao do momento da execução, inclusive após
  alteração ou remoção da associação/definição/campo.
- **SC-007**: Execuções de pré-avaliação anteriores à entrega continuam consultáveis
  sem erro.
- **SC-008**: O upgrade e o downgrade de cada migração desta feature deixam o banco em
  estado consistente, verificado por teste.
- **SC-009**: A suíte de testes permanece verde, com nova cobertura para a autorização
  de triagem, a ausência da esteira legada, o snapshot de conteúdo e o agrupamento de
  observabilidade.
- **SC-010**: As demonstrações do ciclo (submissão, triagem, observabilidade de IA)
  operam de ponta a ponta contra a API real com as contas semeadas, sem depender de
  endpoints removidos.

## Assumptions

- O modelo de RBAC existente (perfis de acesso, permissões, vínculo perfil→permissão,
  atribuição usuário→perfil, reavaliação por requisição) é reutilizado como está; esta
  feature apenas adiciona um perfil, uma permissão e vínculos.
- "Administração" corresponde ao perfil de sistema **Administrador** já existente; não
  é criado um perfil novo para ela.
- O fluxo de roteamento da pré-avaliação (positivo → triagem; negativo → proponente;
  intervenção direta) e o status `AI_PRE_EVALUATION` da submissão permanecem
  inalterados.
- O editor de templates de formulário, o provedor de modelos de IA e a configuração de
  avaliações (biblioteca, versionamento, modo de teste) permanecem inalterados.
- Nenhum endpoint novo é criado para viabilizar demonstrações; as demos consomem a API
  real e são ajustadas apenas para não depender do que foi removido.
- Processos e submissões criados antes desta feature podem ter registros do formato
  legado; esses registros são tratados como histórico imutável, não migrados.
- A conta de triagem semeada (`triage_evaluator`, e-mail do domínio BraCVAM) é a
  representação do papel BraCVAM na massa de demonstração.

## Out of Scope

- Alterar a regra de consolidação ou o roteamento fixo da pré-avaliação (Spec 013).
- Alterar o editor de templates de formulário (Spec 012) ou a configuração de
  avaliações por IA (Spec 013).
- Introduzir notificação ativa (push/e-mail) ao proponente.
- Redefinir o papel "Grupo Gestor" ou "Revisor" além de deixá-los explicitamente
  fora da triagem.
- Migrar dados históricos do formato legado para o novo formato.
- Qualquer mudança no provedor de modelos, camadas ou seleção de modelo.

# Feature Specification: Avaliação Configurável por IA na Submissão e Triagem (Fechamento da Versão 1)

**Feature Branch**: `013-configurable-ai-evaluation`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Preciso fechar uma versão do projeto. Hoje existe um sistema para controlar processos, etapas e tarefas; vamos focar apenas na etapa de Submissão e Triagem de um método. Parte do problema é ter um formulário dinâmico capaz de contemplar toda a complexidade do processo atual, incrementado com auditoria e facilidades, e agora com análises por IA. O proponente sempre passa pela IA na primeira vez; após um retorno negativo pode contestar a IA e enviar direto para um representante humano do BraCVAM. O que a IA avaliou precisa ser apresentado ao BraCVAM. Leitura de documentos, imagens e OCR permanecem mockados. O ponto central é separar 'este campo pode ser avaliado por IA?' de 'como exatamente este campo deve ser avaliado?', com uma configuração assistida em linguagem natural. A IA produz evidências e uma pré-avaliação; o sistema aplica regras institucionais; o humano toma a decisão final."

## Contexto e Direcionamento

Esta especificação fecha a **Versão 1** do PIVMA restringindo o escopo à **Fase 1 — Submissão e Triagem**. Ela consolida e substitui o comportamento provisório da Spec 010 (esteira de IA mock com veredito fixo por campo) por uma avaliação **dirigida por configuração**, reutiliza o editor de templates da Spec 012 e preserva a observabilidade da Spec 010 (`logs/application/`, `logs/ai/`, retenção de 7 dias, streaming administrativo).

O planejamento (`plan.md`) deve manter o código simples e alinhado ao padrão atual: orquestração escondida atrás de um motor de pipeline único; um **provedor de modelos** injetado via `Depends` do FastAPI (no padrão de `src/pivma/dependencies.py`), que encapsula o LangChain/OpenAI e expõe camadas nomeadas (extração, rápido, raciocínio); e substituição por fake nos testes para não gastar tokens. Os detalhes de implementação não fazem parte dos requisitos abaixo, mas o provedor e sua injeção são requisito (ver FR-024a–FR-024d).

Os três documentos de organização de sprints em `.docs/` orientam o faseamento da entrega:

- **Sprint 01 — Fundação**: avaliação configurável substitui a fixa; submissão dispara avaliação automática; roteamento e retorno ao proponente definidos.
- **Sprint 02 — Operação humana, relatórios e auditoria**: apresentação ao proponente e ao BraCVAM; imutabilidade; reconstrução da execução.
- **Sprint 03 — Configuração avançada e evolução**: assistente de configuração; biblioteca de avaliações; versionamento; modo de teste; métricas de concordância.

## Clarifications

### Session 2026-09-09

- **Q1: Escopo do formulário dinâmico**
  - **Decisão**: Esta feature **não estende** o editor/kit de campos da Spec 012. Ela consome o editor de templates da Spec 012 como está e concentra todo o esforço na **configuração de como a IA avalia** o conteúdo do formulário (objetivo, critérios, tipos de verificação, evidência, severidade, alvos, biblioteca, versionamento, modo de teste) e no fluxo de submissão/triagem. A "complexidade do processo atual" é atendida pela camada de configuração de avaliação, orientada pela conversa anexada ao pedido, e não por novos tipos de campo.
- **Q2: Roteamento após a avaliação da IA (regras institucionais)**
  - **Decisão**: O roteamento é **fixo e embutido**, sem editor de regras nesta versão. Fluxo padrão: Proponente submete o formulário → a resposta é avaliada pela IA → **resultado positivo** encaminha para a triagem do BraCVAM → **resultado negativo** retorna ao Proponente. No retorno, o Proponente pode **corrigir e reenviar** (nova avaliação da IA) ou **ignorar os conselhos da IA e solicitar intervenção direta do BraCVAM** (encaminha para triagem preservando o relatório da IA). A IA nunca registra a consequência regulatória; ela apenas produz o resultado que aciona esse roteamento fixo.
- **Q3: Profundidade da análise e das referências normativas**
  - **Decisão**: Referências normativas nesta versão são apenas **entradas versionadas com metadados** (identificador, rótulo, versão, data) para rastreabilidade e análise de impacto — **sem** ingestão do texto da norma e **sem** banco vetorial.
  - **Superseded pela Session 2026-09-10 quanto à execução da análise**: critérios sobre conteúdo **textual** passam a usar um **modelo real da OpenAI via LangChain** (o sistema já entra em produção). Permanece **mockado com conclusão negativa/indeterminada** apenas o que depende de leitura de documento, OCR e análise de imagem — capacidades ainda inexistentes.

### Session 2026-09-10

- **Q: A análise de conteúdo textual usa modelo real ou fica mockada nesta versão?** → A: **Modelo real da OpenAI via LangChain** — a versão entra em produção e precisa gerar resultados de verdade para texto. Só documento/OCR/imagem seguem mockados com resultado negativo/indeterminado.
- **Q: Como o sistema seleciona o modelo por tipo de trabalho?** → A: Um **provedor de modelos** (`AI_PROVIDER`) expõe camadas nomeadas — **extração**, **rápido** (classificação: presença/conformidade) e **raciocínio** (qualidade/comparação/consistência) — e escolhe a camada conforme a etapa/tipo de critério. Cada camada é `ChatOpenAI` com `temperature=0` e nome de modelo configurável (ex.: `gpt-5.4-nano` para extração/rápido, `gpt-5.4-mini` para raciocínio); o ajuste fino dos modelos é posterior.
- **Q: Como o provedor é consumido pela API e nos testes?** → A: É uma **dependência injetável** no padrão de `src/pivma/dependencies.py` (como `Session`), lendo `OPENAI_API_KEY` via `pydantic-settings`. Os testes **substituem** o provedor por um fake/stub — nenhuma chamada externa e nenhum token gasto em `unit`/`api`/CI; um conjunto mínimo de testes de integração real fica isolado e desligado por padrão.
- **Q: O que as demonstrações precisam cobrir?** → A: **Dois módulos** em `demos/`: (1) configuração das avaliações **diretamente pelo editor de formulário**; (2) configuração **pela biblioteca de avaliações**. Ambos operam contra a API real em `http://localhost:8000` mostrando os dados reais do banco sendo alterados. **Nada** pode ser criado (endpoint, atalho, dado) só para viabilizar as demos — elas são a última etapa de validação.
- **Q: A pré-avaliação na submissão roda síncrona ou assíncrona?** → A: **Assíncrona**. A submissão confirma imediatamente com status "pré-avaliação em andamento"; o processamento (chamadas reais à OpenAI) ocorre em segundo plano; o proponente acompanha o status e é informado quando o resultado fica pronto. O roteamento fixo (positivo → triagem; negativo → proponente) é aplicado ao final do processamento em background.
- **Q: O que torna o resultado consolidado negativo?** → A: **Negativo quando há pelo menos uma não conformidade de severidade alta ou crítica.** Não conformidades de severidade baixa/média, resultados parciais e indeterminados **não** barram o proponente — viram alertas apresentados na triagem. Um critério apenas indeterminado nunca torna o resultado negativo.
- **Nomenclatura**: os nomes das camadas do provedor de modelos (extração / rápido / raciocínio) são indicativos e podem ser adaptados ao vocabulário do projeto na implementação.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configuração assistida de avaliação pelo BraCVAM (Priority: P1)

Como Administrador ou Gestor do BraCVAM, quero descrever em linguagem natural **o que a IA deve verificar** em um conteúdo do formulário, receber uma sugestão de critérios estruturados que eu possa aceitar, editar, remover ou complementar, e definir para cada critério o tipo de verificação, a evidência exigida e a severidade — sem escrever prompts nem escolher modelo, tokens ou parâmetros — para transformar conhecimento regulatório em uma avaliação operacional versionada.

**Why this priority**: É a capacidade central que substitui o conceito atual de "campo com IA ligada". Sem ela, não existe avaliação dirigida por configuração e todo o restante da feature não tem insumo.

**Independent Test**: Um usuário BraCVAM abre o assistente de configuração, seleciona o alvo (ex.: campo "Procedimento Operacional Padrão"), escreve "Verificar se o POP está detalhado o suficiente para ser executado por outro laboratório", recebe uma lista de critérios sugeridos, ajusta a lista, define severidades e a evidência exigida, e publica a avaliação como versão 1. O sistema confirma a persistência e a avaliação fica disponível para associação a formulários.

**Acceptance Scenarios**:

1. **Given** um usuário BraCVAM autenticado e um alvo de avaliação selecionado, **When** ele informa apenas o objetivo em linguagem natural, **Then** o sistema apresenta uma proposta de critérios estruturados em linguagem de negócio, cada um com um tipo de verificação sugerido, e permite aceitar todos, editar, remover ou adicionar critérios.
2. **Given** um critério em edição, **When** o usuário define seu tipo de verificação (presença, conformidade, qualidade, comparação ou consistência entre campos), a evidência exigida e a severidade, **Then** essas definições são preservadas no critério sem exigir qualquer parâmetro técnico de IA.
3. **Given** uma avaliação em rascunho com pelo menos um critério, **When** o usuário publica a avaliação, **Then** o sistema registra a versão 1 como imutável e disponível para uso, e nenhuma edição posterior altera essa versão.
4. **Given** um usuário sem perfil BraCVAM, **When** tenta criar ou editar uma avaliação, **Then** o sistema rejeita a operação com erro de autorização.
5. **Given** o modo simples da configuração, **When** o usuário responde apenas "o que verificar?", "o que significa estar correto?" e "o que fazer quando houver problema?", **Then** o sistema completa internamente os demais parâmetros com padrões e gera uma avaliação válida.

---

### User Story 2 - Pré-avaliação automática obrigatória na submissão (Priority: P2)

Como Proponente, quero que cada submissão do formulário passe automaticamente por uma pré-avaliação da IA (processada em segundo plano) e receber um resultado compreensível — quantos critérios foram avaliados, quais estão conformes, quais não, quais ficaram indeterminados, com a evidência de cada apontamento — para corrigir problemas antes da triagem humana.

**Why this priority**: Materializa a regra de negócio "toda submissão passa obrigatoriamente pela avaliação IA" e entrega valor imediato ao proponente; depende da configuração da US1.

**Independent Test**: Um proponente submete um formulário cujo template tem avaliações associadas. O envio confirma na hora com status "pré-avaliação em andamento"; em segundo plano o sistema executa a pré-avaliação, persiste o resultado e, quando pronto, apresenta ao proponente uma síntese com a contagem por conclusão e a lista de pontos que exigem atenção, cada um com critério, conclusão, evidência e recomendação.

**Acceptance Scenarios**:

1. **Given** um formulário com avaliações associadas sendo submetido pelo proponente, **When** ele conclui o envio, **Then** o sistema confirma imediatamente, marca a submissão como "pré-avaliação em andamento" e dispara o processamento em segundo plano, persistindo o relatório vinculado àquela execução quando concluído.
2. **Given** uma pré-avaliação concluída, **When** o proponente visualiza o resultado, **Then** vê uma síntese ("N critérios avaliados; X conformes; Y parcialmente conformes; Z não conformes; W indeterminados") e uma lista expansível de pontos de atenção com critério, conclusão, evidência (trecho/localização quando disponível), justificativa, severidade e recomendação.
3. **Given** critérios sobre **conteúdo textual**, **When** a pré-avaliação é executada, **Then** o sistema usa um **modelo real da OpenAI via LangChain** e produz conclusões genuínas por critério (conforme / não conforme / parcial / indeterminado), com a evidência textual usada.
4. **Given** critérios cujo alvo depende de **leitura de documento, OCR ou análise de imagem**, **When** a pré-avaliação é executada, **Then** o resultado é explicitamente "não foi possível determinar" (capacidade mockada), nunca uma conclusão positiva simulada.
5. **Given** uma pré-avaliação **sem** nenhuma não conformidade de severidade alta ou crítica, **When** a execução conclui, **Then** o resultado consolidado é **positivo** e o processo avança automaticamente para a triagem do BraCVAM, levando junto os alertas de menor severidade.
6. **Given** uma pré-avaliação com **pelo menos uma** não conformidade de severidade alta ou crítica, **When** a execução conclui, **Then** o resultado consolidado é **negativo**, a submissão **retorna ao proponente** com o relatório, sem gerar tarefa de triagem ainda, e o proponente passa a ter as opções da User Story 3.
7. **Given** uma pré-avaliação em que todos os critérios ficaram indeterminados (ex.: só há critérios sobre documento/OCR), **When** a execução conclui, **Then** o resultado consolidado é **positivo** (nenhuma não conformidade alta/crítica) e segue para a triagem com os indeterminados como alertas.
8. **Given** uma submissão de um formulário sem nenhuma avaliação associada, **When** o proponente submete, **Then** a submissão prossegue normalmente para a triagem com um relatório de pré-avaliação vazio e sem erro.
9. **Given** uma falha do modelo/serviço de IA durante a execução, **When** a pré-avaliação não pode ser concluída, **Then** a submissão não fica bloqueada indefinidamente, a execução é registrada como falha e a triagem humana pode prosseguir.
10. **Given** o resultado apresentado ao proponente, **When** a pré-avaliação indica não conformidades, **Then** a confiança estatística não é exibida como indicador primário; a interface prioriza conclusão + evidência + necessidade de análise humana.

---

### User Story 3 - Retorno ao proponente e solicitação de intervenção direta do BraCVAM (Priority: P3)

Como Proponente que recebeu um retorno negativo da pré-avaliação, quero poder **corrigir e reenviar** o formulário (passando por nova avaliação da IA) ou **ignorar os conselhos da IA e solicitar a intervenção direta de um representante humano do BraCVAM**, preservando o resultado original da IA, para não ficar preso a uma conclusão automática que considero incorreta.

**Why this priority**: É uma exigência explícita do produto e o contrapeso de governança à automação; depende do resultado da US2.

**Independent Test**: Após uma pré-avaliação negativa, o proponente escolhe "solicitar intervenção direta do BraCVAM" em vez de "corrigir e reenviar", registra opcionalmente uma justificativa, e o sistema encaminha a submissão para a fila de triagem mantendo o relatório original da IA intacto e anexando a solicitação.

**Acceptance Scenarios**:

1. **Given** uma pré-avaliação negativa apresentada ao proponente, **When** ele tem as opções disponíveis, **Then** o sistema oferece exatamente duas ações distintas e rastreáveis: **corrigir e reenviar** e **ignorar os conselhos da IA e solicitar intervenção direta do BraCVAM**.
2. **Given** o proponente que escolhe corrigir e reenviar, **When** ele conclui um novo envio, **Then** o sistema cria uma nova execução da submissão, dispara uma **nova pré-avaliação** e o ciclo da User Story 2 se repete.
3. **Given** o proponente que escolhe solicitar intervenção direta, **When** ele confirma (com justificativa opcional), **Then** o sistema encaminha a submissão para a triagem do BraCVAM sem exigir novo preenchimento do formulário.
4. **Given** uma solicitação de intervenção direta registrada, **When** ela é persistida, **Then** o relatório original da IA permanece imutável e associado à execução, e a solicitação fica anexada como registro separado com autor e data.
5. **Given** uma submissão já encaminhada por solicitação de intervenção direta, **When** o proponente tenta solicitar novamente para a mesma execução, **Then** o sistema impede duplicidade e mantém a solicitação vigente.

---

### User Story 4 - Triagem assistida do BraCVAM com a IA como evidência auxiliar (Priority: P4)

Como Triador do BraCVAM, quero visualizar, na tarefa de triagem, a pré-avaliação da IA como evidência auxiliar — dados avaliados, critérios utilizados, conclusão e evidência de cada critério, severidade, referência normativa, versão da avaliação, data e identificação da execução — e registrar minha concordância ou discordância por critério, para tomar a decisão regulatória final de forma fundamentada e auditável.

**Why this priority**: Fecha o ciclo de valor: a IA reduz trabalho manual sem substituir a decisão humana. Depende das US1–US3.

**Independent Test**: Um triador abre uma submissão em triagem, consulta o painel de pré-avaliação da IA, expande cada critério para ver conclusão e evidência, marca "concordo"/"discordo"/"inconclusivo" com motivo opcional em alguns critérios, e emite a decisão de triagem (aprovar, rejeitar ou solicitar diligência). O sistema registra a decisão humana como final e preserva a análise da IA.

**Acceptance Scenarios**:

1. **Given** uma submissão em triagem com pré-avaliação registrada, **When** o triador abre a tarefa, **Then** vê o painel da IA com: conteúdo avaliado, lista de critérios, conclusão e evidência de cada um, severidade, referência normativa associada, versão da avaliação utilizada, data/hora e identificador da execução.
2. **Given** o painel da IA aberto, **When** o triador registra concordância, discordância ou "inconclusivo" para um critério, opcionalmente com motivo, **Then** o sistema persiste esse feedback vinculado ao critério, ao triador e à execução, sem alterar o resultado original da IA.
3. **Given** o resultado consolidado da pré-avaliação, **When** o sistema aplica o roteamento fixo, **Then** um resultado positivo encaminha para a triagem e um negativo retorna ao proponente; a IA nunca registra por si uma aprovação, rejeição ou diligência, e a decisão de triagem permanece integralmente humana.
4. **Given** o triador diante da síntese, **When** ele emite a decisão de triagem, **Then** a decisão é atribuída ao usuário humano, é registrada como final e o processo transiciona conforme a Spec 004 (aprovado, rejeitado/encerrado ou nova execução da submissão para diligência).
5. **Given** um usuário com conflito de interesse vigente no processo, **When** tenta registrar feedback ou decisão de triagem, **Then** o sistema bloqueia a ação (consistente com as regras de conflito já existentes).

---

### User Story 5 - Biblioteca de avaliações reutilizáveis e versionamento imutável (Priority: P5)

Como Gestor do BraCVAM, quero manter uma biblioteca de avaliações reutilizáveis (ex.: "Verificação de estrutura de POP", "Verificação de resumo metodológico") e associá-las a um ou mais alvos em qualquer formulário, e quero que qualquer alteração em uma avaliação já utilizada gere uma nova versão, para reduzir duplicação e nunca alterar retroativamente a interpretação histórica.

**Why this priority**: Reduz o custo operacional de configurar tudo campo a campo e é a base de governança para auditoria ao longo do tempo.

**Independent Test**: Um gestor cria uma avaliação na biblioteca, associa-a ao campo "POP" de dois templates diferentes, edita a avaliação (adicionando um critério) e o sistema cria a versão 2; submissões feitas antes da edição continuam associadas à versão 1.

**Acceptance Scenarios**:

1. **Given** a biblioteca de avaliações, **When** o gestor cria uma avaliação reutilizável, **Then** ela pode ser associada a alvos em múltiplos formulários sem ser copiada.
2. **Given** uma avaliação já utilizada em pelo menos uma submissão, **When** o gestor a edita e salva, **Then** o sistema cria uma nova versão e mantém a versão anterior intacta e referenciada pelas execuções que a usaram.
3. **Given** um alvo de avaliação, **When** o gestor associa uma avaliação, **Then** o alvo pode ser um campo, um conjunto de campos, um documento, o formulário inteiro ou dados do processo — a avaliação não é propriedade exclusiva de um campo.
4. **Given** o atributo `ai_evaluation_enabled` de um campo, **When** interpretado nesta versão, **Then** ele significa apenas "este campo está disponível para avaliações automatizadas", podendo ter zero, uma ou várias avaliações associadas.
5. **Given** uma avaliação da biblioteca removida, **When** ela ainda está associada a um template ativo ou a execuções passadas, **Then** a remoção é lógica e não quebra templates existentes nem a reconstrução de execuções.

---

### User Story 6 - Modo de teste antes da publicação (Priority: P6)

Como Administrador do BraCVAM configurando uma avaliação, quero executá-la sobre um conteúdo de exemplo antes de publicá-la, ver o resultado por critério (conclusão, evidência, interpretação) e iterar sobre as definições, para publicar apenas avaliações que produzem resultados adequados.

**Why this priority**: Reduz drasticamente o risco de configurações aparentemente corretas que geram avaliações ruins em produção; é um controle de qualidade da configuração.

**Independent Test**: Um administrador com uma avaliação em rascunho fornece um texto/exemplo, aciona "testar avaliação", vê o resultado por critério, ajusta a definição de um critério mal interpretado, testa de novo e então publica.

**Acceptance Scenarios**:

1. **Given** uma avaliação em rascunho, **When** o administrador fornece um conteúdo de exemplo e aciona o teste, **Then** o sistema executa a avaliação e exibe, por critério, a conclusão, a evidência encontrada e a interpretação, sem afetar nenhuma submissão real.
2. **Given** um resultado de teste considerado incorreto, **When** o administrador ajusta a definição de um critério, **Then** ele pode reexecutar o teste quantas vezes forem necessárias antes de publicar.
3. **Given** uma avaliação que nunca foi testada, **When** o administrador tenta publicá-la, **Then** o sistema alerta que nenhuma execução de teste foi realizada (sem necessariamente bloquear, conforme política definida no plano).
4. **Given** uma avaliação em rascunho, **When** uma submissão real é processada, **Then** a avaliação em rascunho nunca é aplicada — apenas versões publicadas participam de pré-avaliações reais.

---

### User Story 7 - Demonstrações interativas (AGENTS.md) (Priority: P7)

Como Avaliador técnico ou Administrador, quero **dois módulos** de demonstração em `demos/` — (1) configuração das avaliações **diretamente pelo editor de formulário** e (2) configuração **pela biblioteca de avaliações** — operando contra a API real em `http://localhost:8000`, para ver os dados reais do banco sendo alterados e validar de ponta a ponta o comportamento entregue.

**Why this priority**: Cumpre o critério normativo do `AGENTS.md` de que a entrega só se conclui com demonstração funcional e seed correspondente. É a **última etapa** de validação.

**Independent Test**: A partir de `demos/index.html`, abrir cada módulo, usar a massa de dados de `scripts/seeds/`, e: no módulo do editor de formulário, associar/ajustar avaliações em campos e ver a persistência; no módulo da biblioteca, criar uma avaliação reutilizável, testá-la, publicá-la e associá-la a um formulário — tudo refletindo o estado real do backend.

**Acceptance Scenarios**:

1. **Given** o catálogo `demos/index.html`, **When** o usuário acessa o índice, **Then** os dois módulos desta feature estão catalogados e funcionais.
2. **Given** o módulo "configuração pelo editor de formulário" conectado à API real, **When** o usuário associa ou edita uma avaliação em um campo e salva, **Then** a alteração é persistida e relida do banco via API.
3. **Given** o módulo "configuração pela biblioteca de avaliações" conectado à API real, **When** o usuário cria, testa, publica e associa uma avaliação, **Then** cada passo altera o estado real do backend e é observável na interface.
4. **Given** o código de ambos os módulos, **When** inspecionado, **Then** reside estritamente em `demos/`, é descartável e **não** depende de nenhum endpoint, atalho ou dado criado apenas para a demonstração.
5. **Given** a API real rodando em `http://localhost:8000`, **When** as demos executam, **Then** consomem exclusivamente essa API com autenticação real, sem mocks de backend.

---

### Edge Cases

- **Formulário sem avaliações associadas**: submissão prossegue direto para a triagem; relatório de pré-avaliação vazio; triagem humana normal.
- **Critério sobre texto**: avaliado por modelo real da OpenAI via LangChain; conclusão genuína (conforme / não conforme / parcial / indeterminado).
- **Critério que depende de documento / OCR / imagem**: sempre "não foi possível determinar" (capacidade mockada); nunca conclusão positiva simulada.
- **Evidência exigida não encontrada / informação ausente**: conclusão segue o comportamento configurado no critério ("não conforme" ou "indeterminado").
- **Critério de consistência entre campos com um dos campos vazio**: resultado "indeterminado" (não torna o resultado consolidado negativo).
- **Só não conformidades de severidade baixa/média**: resultado consolidado **positivo**; as não conformidades viram alertas na triagem, sem barrar o proponente.
- **Sem `OPENAI_API_KEY` ou `AI_PROVIDER=mock`**: o sistema usa o provedor fake/local e as execuções de texto se resolvem de forma indeterminada — nunca falha silenciosa nem conclusão positiva.
- **Erro/timeout do modelo da OpenAI durante a pré-avaliação**: execução marcada como falha, evento registrado, submissão não travada; o proponente é informado e a submissão pode ser encaminhada à triagem humana.
- **Referência normativa atualizada após execuções**: o sistema permite identificar quais avaliações e execuções usaram a versão anterior da referência (metadados, sem reexecução).
- **Proponente solicita intervenção direta e depois tenta corrigir e reenviar**: precedência única — a submissão já encaminhada segue para a triagem; um novo envio cria nova execução da submissão com nova pré-avaliação, sem estados contraditórios.
- **Avaliação publicada editada**: sempre gera nova versão; execuções e templates que apontavam para a versão anterior permanecem íntegros.
- **Avaliação da biblioteca removida enquanto em uso**: exclusão lógica; templates ativos e reconstrução de execuções continuam funcionando.
- **Pré-avaliação demorada**: o envio confirma na hora; o proponente vê "em andamento" e é informado ao concluir. A interface nunca trava aguardando a OpenAI.
- **Proponente sai da tela antes de a pré-avaliação concluir**: ao voltar, encontra o status atualizado (em andamento / concluída / falha) e o relatório se pronto.
- **Reenvio enquanto a execução anterior ainda está "em andamento"**: bloqueado até a conclusão (FR-021d).
- **Reenvio após diligência**: todo reenvio do proponente dispara nova pré-avaliação, seguindo o mesmo roteamento fixo.
- **Conteúdo muito extenso ou binário**: a preparação de dados registra referências/metadados/hashes em vez de serializar conteúdo bruto nos logs.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Configuração de avaliação

- **FR-001**: O sistema MUST permitir que um usuário BraCVAM crie uma **avaliação** a partir de um objetivo descrito em linguagem natural, sem exigir prompt, escolha de modelo, tokens, temperatura ou qualquer parâmetro técnico de IA.
- **FR-002**: O sistema MUST, a partir do objetivo informado, **sugerir** um conjunto de critérios estruturados em linguagem de negócio que o usuário possa aceitar integralmente, editar, remover ou complementar.
- **FR-003**: O sistema MUST permitir definir, para cada critério: um enunciado em linguagem natural, um **tipo de verificação**, a **evidência exigida**, a **severidade** e o **comportamento quando a informação estiver ausente**.
- **FR-004**: O sistema MUST suportar os seguintes tipos de verificação de critério: **presença**, **conformidade**, **qualidade**, **comparação entre informações** e **consistência entre campos**.
- **FR-005**: O sistema MUST suportar critérios **positivos** ("deve conter X"), **negativos** ("não pode conter X") e de **consistência** ("X deve ser consistente com Y").
- **FR-006**: O sistema MUST oferecer um **modo simples** (três perguntas: o que verificar, o que significa estar correto, o que fazer quando houver problema) e um **modo avançado** (fontes/referências, exigência de evidência, critérios de indeterminação, comportamento em ausência de informação, recomendação sugerida ao triador em caso de não conformidade).
- **FR-007**: O sistema MUST permitir associar **referências normativas** a uma avaliação, selecionando-as de um cadastro em vez de copiar o texto da norma.
- **FR-008**: O sistema MUST tratar `ai_evaluation_enabled` de um campo apenas como "disponível para avaliações automatizadas"; a configuração real da avaliação MUST ser independente desse atributo.
- **FR-009**: O sistema MUST permitir que uma avaliação tenha como **alvo** um campo, um conjunto de campos, um documento, o formulário inteiro ou dados do processo, e que um alvo tenha zero, uma ou várias avaliações associadas.
- **FR-010**: O sistema MUST manter uma **biblioteca de avaliações reutilizáveis**, associáveis a alvos em múltiplos formulários sem duplicação da definição.
- **FR-011**: O sistema MUST restringir a criação, edição, publicação e remoção de avaliações a perfis BraCVAM (Administrador / Grupo Gestor), consistente com a Spec 012.

#### Versionamento e governança da configuração

- **FR-012**: O sistema MUST versionar avaliações; uma versão **publicada** é imutável.
- **FR-013**: O sistema MUST criar uma **nova versão** ao salvar alterações em uma avaliação já utilizada em qualquer submissão, preservando a versão anterior e suas associações históricas.
- **FR-014**: O sistema MUST registrar, para cada avaliação e versão: autor, data de criação, referências utilizadas e a versão de cada referência no momento da criação.
- **FR-015**: O sistema MUST permitir identificar quais avaliações e execuções utilizaram uma determinada versão de uma referência normativa.
- **FR-016**: O sistema MUST usar exclusão lógica para avaliações e referências, sem quebrar templates ativos nem a reconstrução de execuções.

#### Modo de teste

- **FR-017**: O sistema MUST permitir executar uma avaliação em rascunho sobre um **conteúdo de exemplo** fornecido pelo usuário, exibindo o resultado por critério (conclusão, evidência, interpretação), sem afetar submissões reais.
- **FR-018**: O sistema MUST permitir reexecutar o teste após ajustes na configuração, quantas vezes forem necessárias, antes da publicação.
- **FR-019**: O sistema MUST NOT aplicar avaliações em rascunho a pré-avaliações de submissões reais — apenas versões publicadas participam.
- **FR-020**: O sistema SHOULD sinalizar, na publicação, quando nenhuma execução de teste foi realizada para aquela avaliação.

#### Execução da pré-avaliação

- **FR-021**: O sistema MUST disparar automaticamente a pré-avaliação por IA a cada envio de um formulário que tenha avaliações associadas.
- **FR-021a**: A pré-avaliação MUST ser **assíncrona**: o envio do formulário confirma imediatamente e a submissão fica com status "pré-avaliação em andamento"; o processamento ocorre em segundo plano.
- **FR-021b**: O sistema MUST permitir que o proponente **acompanhe o status** da pré-avaliação (em andamento / concluída / falha) e MUST informá-lo quando o resultado ficar disponível.
- **FR-021c**: O roteamento fixo (positivo → triagem; negativo → proponente) MUST ser aplicado ao **final** do processamento em background, não no momento do envio.
- **FR-021d**: Enquanto uma pré-avaliação estiver em andamento para uma submissão, o sistema MUST NOT aceitar novo envio da mesma execução nem gerar tarefa de triagem para ela.
- **FR-022**: O sistema MUST executar internamente as etapas de preparação de dados, extração de evidências, avaliação dos critérios, síntese e geração do relatório, mantendo essa orquestração escondida atrás de um motor de pipeline único.
- **FR-023**: O sistema MUST produzir, para cada critério avaliado, uma **conclusão** compatível com o tipo de verificação, incluindo sempre um estado equivalente a **"não foi possível determinar"**.
- **FR-024**: Para critérios sobre **conteúdo textual** (texto digitado, resumo, valores de campos, consistência entre campos), o sistema MUST executar a avaliação com um **modelo real da OpenAI acessado via LangChain**, produzindo conclusões genuínas compatíveis com o tipo de verificação.
- **FR-024a**: O sistema MUST expor um **provedor de modelos** com camadas nomeadas — **extração**, **rápido** (classificação: presença, conformidade) e **raciocínio** (qualidade, comparação, consistência) — e selecionar a camada conforme a etapa do pipeline e o tipo de critério.
- **FR-024b**: Cada camada MUST ser um cliente `ChatOpenAI` com `temperature = 0` e **nome de modelo configurável** via `pydantic-settings` (ex.: `gpt-5.4-nano` para extração/rápido, `gpt-5.4-mini` para raciocínio); a `OPENAI_API_KEY` MUST vir de `Settings`, nunca de leitura ad hoc de ambiente.
- **FR-024c**: O provedor MUST ser uma **dependência injetável** no padrão de `src/pivma/dependencies.py` (equivalente a `Session`), consumida pelos routers e pelo motor de pipeline via `Depends`, e MUST ser **substituível por um fake/stub** nos testes — sem chamadas externas e sem consumo de tokens em `unit`, `api` e CI.
- **FR-024d**: Um seletor de configuração (`AI_PROVIDER`) MUST permitir alternar entre a implementação real da OpenAI e uma implementação fake/local; o comportamento padrão em ambientes de desenvolvimento e CI MUST NOT realizar chamadas externas.
- **FR-024e**: Critérios cujo alvo dependa de **leitura de documento, OCR ou análise de imagem** MUST retornar resultado explicitamente "não foi possível determinar" (capacidade mockada nesta versão); NUNCA uma conclusão positiva simulada. A interface do provedor para essas capacidades MUST ficar preparada para implementação futura.
- **FR-025**: O sistema MUST registrar, por critério: conclusão, evidência (trecho e localização quando disponível), justificativa, severidade e recomendação.
- **FR-026**: O sistema MUST tratar **confiança da inferência**, **completude da evidência** e **qualidade do documento analisado** como informações distintas; a confiança estatística MUST NOT ser o indicador primário apresentado.
- **FR-027**: O sistema MUST concluir a submissão normalmente, avançando direto para a triagem com relatório vazio, quando o formulário não tiver avaliações associadas.
- **FR-028**: O sistema MUST tratar falhas do serviço de avaliação sem bloquear a submissão indefinidamente: a execução é registrada como falha e a submissão pode seguir para a triagem humana.
- **FR-029**: O sistema MUST disparar uma nova pré-avaliação a **cada envio ou reenvio do formulário pelo proponente** (primeira submissão, correção após retorno negativo, reenvio após diligência). A pré-avaliação só é dispensada quando o proponente escolhe explicitamente solicitar a intervenção direta do BraCVAM.

#### Roteamento e decisão

- **FR-030**: O sistema MUST consolidar os resultados de critério em um **resultado da pré-avaliação** por regra fixa e embutida: **negativo** quando houver **pelo menos uma não conformidade de severidade alta ou crítica**; **positivo** caso contrário. Não conformidades de severidade baixa/média, resultados parciais e indeterminados NÃO tornam o resultado negativo — são registrados como **alertas** exibidos na triagem. Não há editor de regras nesta versão.
- **FR-030a**: Após a pré-avaliação assíncrona, o sistema MUST aplicar o roteamento fixo: resultado **positivo** encaminha a submissão para a triagem do BraCVAM; resultado **negativo** retorna a submissão ao proponente com o relatório.
- **FR-031**: O sistema MUST NOT permitir que a IA registre por si uma aprovação, rejeição, diligência ou qualquer consequência regulatória; a IA apenas produz os resultados de critério que alimentam a regra de consolidação.
- **FR-032**: O sistema MUST atribuir toda decisão de triagem a um **usuário humano** e registrá-la como final, com a transição de processo conforme a Spec 004.
- **FR-033**: O sistema MUST manter o ramo "resultado positivo → triagem" implementado e testável desde esta versão, exercitado sempre que nenhuma não conformidade alta/crítica for encontrada.

#### Fluxo do proponente

- **FR-034**: O sistema MUST apresentar ao proponente uma **síntese compreensível** da pré-avaliação: contagem por conclusão e lista expansível de pontos de atenção com critério, conclusão, evidência, justificativa, severidade e recomendação.
- **FR-035**: Diante de um resultado negativo, o sistema MUST oferecer ao proponente exatamente duas opções distintas e rastreáveis: **corrigir e reenviar** (nova pré-avaliação) e **ignorar os conselhos da IA e solicitar a intervenção direta do BraCVAM**.
- **FR-036**: O sistema MUST permitir que o proponente **solicite a intervenção direta do BraCVAM** após uma pré-avaliação negativa, registrando justificativa opcional, encaminhando a submissão para a triagem sem novo preenchimento do formulário.
- **FR-037**: O sistema MUST preservar o **relatório original da IA** imutável ao registrar a solicitação de intervenção direta, anexando-a como registro separado com autor e data.
- **FR-038**: O sistema MUST impedir solicitação de intervenção direta duplicada para a mesma execução de pré-avaliação.

#### Triagem e feedback humano

- **FR-039**: O sistema MUST apresentar ao triador do BraCVAM, na tarefa de triagem: conteúdo avaliado, critérios utilizados, conclusão e evidência de cada critério, severidade, referência normativa, **versão da avaliação utilizada**, data/hora da execução e **identificador da execução**.
- **FR-040**: O sistema MUST permitir que o triador registre, por critério, **concordo / discordo / inconclusivo**, com motivo opcional, vinculado ao critério, ao triador e à execução, sem alterar o resultado original da IA.
- **FR-041**: O sistema MUST disponibilizar métricas de **concordância humana** com a IA (taxa de concordância, critérios mais problemáticos), para fins de auditoria da qualidade.
- **FR-042**: O sistema MUST NOT usar o feedback humano automaticamente para treinar modelos; o uso é restrito a auditoria e métricas.
- **FR-043**: O sistema MUST bloquear feedback e decisão de triagem de usuários com conflito de interesse vigente no processo (consistente com as regras existentes).

#### Auditoria, rastreabilidade e observabilidade

- **FR-044**: O sistema MUST registrar, para cada **execução de pré-avaliação**: a avaliação e a versão utilizadas, o conteúdo avaliado, o serviço/modelo que realizou a análise, os critérios executados, as evidências encontradas, o resultado e, posteriormente, a decisão humana.
- **FR-045**: O sistema MUST permitir reconstruir a resposta à pergunta "qual avaliação automática foi realizada e qual informação sustentou essa conclusão?" para qualquer submissão.
- **FR-046**: O sistema MUST NOT permitir alteração retroativa de execuções de pré-avaliação já realizadas.
- **FR-047**: O sistema MUST preservar a observabilidade da Spec 010: índice operacional em `logs/application/`, log granular de IA em `logs/ai/`, retenção de 7 dias e streaming administrativo restrito a Administradores, agrupando etapas por execução de pipeline (`correlation_id`).
- **FR-048**: Novos registros relacionais MUST herdar do mecanismo de auditoria existente (`AuditMixin`) e usar exclusão lógica.

#### Formulário dinâmico

- **FR-049**: O sistema MUST operar a Fase 1 (Submissão e Triagem) com o formulário dinâmico já provido pela Spec 012 (seções, tipos de campo, obrigatoriedade, regras de validação), **consumindo-o como está**.
- **FR-050**: Esta feature MUST NOT estender o editor/kit de campos (novos tipos de campo, campos compostos, lógica condicional); a "complexidade do processo atual" é endereçada pela camada de configuração de avaliação por IA, não por novos recursos de formulário.

### Key Entities *(include if feature involves data)*

- **Avaliação (Evaluation Definition)**: intenção regulatória de verificar algo; possui nome, descrição, modo (simples/avançado), pertence à biblioteca, tem uma ou mais versões.
- **Versão da Avaliação (Evaluation Version)**: instância imutável e publicável de uma avaliação; congela critérios, referências e seus números de versão; guarda autor e datas.
- **Critério (Criterion)**: unidade de verificação dentro de uma versão; enunciado em linguagem natural, tipo de verificação, polaridade (positivo/negativo/consistência), evidência exigida, severidade, comportamento em ausência de informação.
- **Alvo da Avaliação (Evaluation Target)**: o que a avaliação consome — campo, conjunto de campos, documento, formulário inteiro ou dados do processo; a associação vive fora do campo.
- **Referência Normativa (Normative Reference)**: entrada versionada de cadastro (ex.: OECD 442B) com identificador, rótulo, versão e data; associável a avaliações.
- **Execução de Pré-avaliação (Evaluation Run)**: uma execução da IA para uma submissão/execução de atividade; referencia a versão da avaliação, o conteúdo avaliado, o provedor e o nome de cada modelo usado por camada, `correlation_id`, início/fim, custo real e **status** (em andamento / concluída / falha) processado de forma assíncrona.
- **Provedor de Modelos (Model Provider)**: abstração injetável (`Depends`) que encapsula LangChain/OpenAI e expõe as camadas **extração**, **rápido** e **raciocínio**; implementação real (`AI_PROVIDER=openai`) e fake para testes/dev; nomes de modelo e chave lidos de `Settings`.
- **Resultado de Critério (Criterion Result)**: conclusão por critério dentro de uma execução; evidência (trecho, localização), justificativa, recomendação, severidade herdada, confiança (secundária), completude da evidência.
- **Relatório de Pré-avaliação (Pre-evaluation Report)**: síntese consolidada de uma execução, apresentada a proponente e triador; contagem por conclusão, pontos de atenção, alertas de menor severidade, e o **resultado consolidado** (positivo/negativo — negativo sse houver ≥1 não conformidade alta/crítica) que aciona o roteamento fixo.
- **Solicitação de Intervenção Direta (Direct Review Request)**: registro do proponente que ignora os conselhos da IA e encaminha a submissão à triagem humana; autor, data, justificativa opcional; não altera o relatório original.
- **Feedback do Avaliador (Reviewer Feedback)**: concordo/discordo/inconclusivo por critério, com motivo opcional; vinculado a triador, critério e execução.
- **Execução de Teste (Test Run)**: execução de uma avaliação em rascunho sobre conteúdo de exemplo; não afeta submissões reais.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um usuário BraCVAM consegue configurar e publicar uma avaliação completa (objetivo + pelo menos 5 critérios com severidade e evidência) **sem escrever nenhum prompt** e sem informar nenhum parâmetro técnico de IA.
- **SC-002**: 100% das primeiras submissões de formulários com avaliações associadas geram um relatório de pré-avaliação persistido e consultável.
- **SC-003**: Para qualquer submissão, o triador do BraCVAM vê, em uma única tela, todos os critérios avaliados com conclusão e evidência de cada um, além da versão da avaliação, data e identificador da execução.
- **SC-004**: Nenhuma consequência regulatória (aprovação, rejeição, diligência) é registrada sem uma ação humana explícita; a IA nunca é registrada como autora da decisão, apenas do resultado que aciona o roteamento fixo.
- **SC-005**: Alterar uma avaliação já utilizada cria uma nova versão em 100% dos casos e não altera nenhum resultado histórico.
- **SC-006**: Um proponente com pré-avaliação negativa alcança a triagem humana em no máximo 2 ações (solicitar intervenção direta → confirmar), sem repreencher o formulário.
- **SC-007**: O triador registra concordância/discordância por critério, e a taxa de concordância humano–IA fica disponível como métrica agregada.
- **SC-008**: 100% das avaliações aplicadas a submissões reais são versões publicadas; nenhuma avaliação em rascunho participa de pré-avaliações reais.
- **SC-009**: Para 100% das execuções de pré-avaliação, é possível reconstruir: versão da configuração, conteúdo avaliado, provedor e modelo por camada, evidências, resultado e decisão humana.
- **SC-010**: Critérios sobre texto são avaliados por modelo real; critérios que dependem de documento/OCR/imagem retornam "não foi possível determinar" em 100% dos casos — nenhuma conclusão positiva falsa.
- **SC-011**: Nenhuma execução da suíte de testes `unit`/`api` nem de CI realiza chamada externa à OpenAI ou consome tokens.
- **SC-012**: Um erro ou timeout do modelo da OpenAI nunca impede a triagem humana de uma submissão.
- **SC-013**: Os dois módulos de demonstração em `demos/` executam contra a API real em `http://localhost:8000` e alteram dados reais do banco, sem qualquer endpoint ou dado criado apenas para a demo.
- **SC-014**: O envio do formulário confirma em menos de 2 segundos independentemente do tempo de resposta da OpenAI; o resultado da pré-avaliação chega depois, com o proponente vendo o status "em andamento" nesse intervalo.

## Assumptions

- O escopo está limitado à **Fase 1 — Submissão e Triagem**; demais fases do processo estão fora de escopo.
- A versão **entra em produção**: critérios sobre texto usam **modelo real da OpenAI via LangChain**. Somente leitura de documento, OCR e análise de imagem seguem mockadas (resultado "não foi possível determinar"). Não há ingestão de texto de normas nem banco vetorial nesta versão.
- Existe `OPENAI_API_KEY` configurada no `.env`, lida via `pydantic-settings`. Os modelos padrão são econômicos (ex.: `gpt-5.4-nano` para extração/rápido, `gpt-5.4-mini` para raciocínio), `temperature=0`, e podem ser reajustados depois por configuração.
- O **provedor de modelos** é uma dependência injetável no padrão de `src/pivma/dependencies.py`; nos testes é substituído por um fake — `unit`/`api`/CI não fazem chamadas externas.
- A configuração de avaliações é restrita a perfis **BraCVAM (Administrador / Grupo Gestor)**, consistente com a Spec 012.
- O **editor de templates de formulário da Spec 012 é reutilizado como está**; esta feature não estende o kit de campos (Q1).
- O **roteamento pós-avaliação é fixo e embutido** (positivo → triagem; negativo → proponente), sem editor de regras (Q2).
- As **referências normativas** são apenas entradas versionadas com metadados (identificador, rótulo, versão, data), para rastreabilidade e análise de impacto (Q3).
- A **observabilidade da Spec 010** (logs/application, logs/ai, retenção de 7 dias, streaming administrativo) é mantida e estendida para a nova execução de pré-avaliação, incluindo provedor/modelo e custo real por etapa.
- A abstração de **armazenamento vetorial** não é criada nesta versão (sem RAG); só a de modelos.
- O **feedback humano** serve apenas para auditoria e métricas de qualidade; nunca é canalizado automaticamente para treinamento.
- **Confiança estatística** é informação secundária e não é apresentada como indicador primário.
- Avaliações **publicadas são imutáveis**; qualquer alteração gera nova versão.
- As **demonstrações** são dois módulos (`demos/`: editor de formulário e biblioteca de avaliações), última etapa da entrega, contra a API real em `http://localhost:8000`, sem nada criado só para viabilizá-las.
- O padrão de testes do projeto (Testcontainers, Factory Boy, AAA, camadas `unit`/`api`/`integration`) e a skill `fastapi-testing-methodology` serão seguidos na implementação.

## Dependencies

- **Spec 004** — Estrutura de processos e Fase 1 (Submissão e Triagem): máquina de estados, `FormInstance`, `Artifact`, `ActivityRun`, decisão de triagem, fluxo de diligência.
- **Spec 010** — Pipeline de IA (mock) e observabilidade em duas camadas; esta feature evolui o `FormAIPipelineEngine` de veredito fixo para dirigido por configuração.
- **Spec 012** — Editor de templates de formulários, seções e atributos simplificados de IA por campo.
- **LangChain + SDK da OpenAI** — novas dependências de runtime para o provedor de modelos (camadas extração/rápido/raciocínio); `OPENAI_API_KEY` via `pydantic-settings`.
- Regras de **conflito de interesse** e **RBAC** já existentes para autorização de configuração, feedback e decisão.

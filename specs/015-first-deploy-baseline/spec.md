# Feature Specification: Pacote de Baseline do Primeiro Deploy

**Feature Branch**: `015-first-deploy-baseline`

**Created**: 2026-09-10

**Status**: Implementado (formulários + seeds completos; padronização das demos parcial — ver `tasks.md` › Status da implementação)

**Input**: User description: "Refatorar o estado base da aplicação que aparece no primeiro deploy: revisar seeds, formulários e demos para uma apresentação do que está pronto. Padronizar as demos (estilo demonstração séria para público não técnico, pouco texto, campos em inglês), garantir que `seed_all` sozinho habilita a demonstração de todos os módulos da pasta `demos/`, e refatorar apenas o formulário da seção inicial dos 5 processos em `src/pivma/templates_data`: simplificar ao máximo os três primeiros (um único campo não vazio), preencher o quarto com um exemplo simples de uso da IA, e converter o quinto para o Formulário Preliminar (FP) real do BraCVAM."

## Overview

Antes da primeira apresentação pública, o estado inicial do sistema — o que aparece
logo após o deploy e a carga de dados — precisa transmitir uma impressão coerente e
profissional. Hoje esse estado é composto por três artefatos que evoluíram de forma
independente e estão desalinhados entre si:

1. **Demos** (`demos/`): seis páginas de demonstração com estilos, textos e instruções
   de seed divergentes; o catálogo (`demos/index.html`) ainda aponta para um
   `DESIGN.md` que foi removido.
2. **Seeds** (`scripts/seeds/`): a carga mestre `seed_all` provisiona usuários,
   processos e uma pré-avaliação de IA, mas depende de nomes de campos específicos dos
   formulários — qualquer mudança nos formulários quebra a carga.
3. **Formulários** (`src/pivma/templates_data/`): cinco templates de processo, cada um
   com um formulário de submissão (seção inicial) hoje preenchido com campos densos e
   fictícios que não servem bem a uma demonstração.

Esta feature entrega um **pacote único e coerente**: demos padronizadas, uma carga
`seed_all` que basta para demonstrar todos os módulos, e os cinco formulários de
submissão redesenhados conforme o propósito de cada demonstração.

## Clarifications

### Session 2026-09-10

- Q: Como o formulário 5 deve tratar elementos do FP que o motor de formulários não representa nativamente (grupos de checkbox, sub-campos condicionais, tabela repetível de confidencialidade, lista de referências)? → A: Aproximar cada elemento pelo tipo suportado mais próximo (múltipla escolha → vários `boolean` ou um `textarea`; "se sim, especifique" → `textarea` sempre visível; tabelas/listas → um `textarea` cada), agrupando por `section`, e registrar cada aproximação como pendência.
- Q: Os rótulos dos formulários e da interface das demos devem ser em inglês ou português? → A: Rótulos dos formulários de submissão (1 a 5) em português; a interface das demos também em português, usando termo em inglês apenas quando não houver equivalente em português de uso corrente.
- Q: Qual a profundidade da padronização das demos? → A: Criar um padrão visual compartilhado (cabeçalho, paleta, tipografia, status da API, botões) e reescrever a estrutura e os textos das 6 páginas para segui-lo, incluindo a limpeza do catálogo.
- Q: O que fazer com os seeds fora da carga mestre que dependem de campos removidos (`seed_form_ai_demo.py`)? → A: Remover os seeds órfãos que não fazem parte do `seed_all`.
- Q: O campo único dos formulários 1 a 3 deve ser um texto curto obrigatório de título do método? → A: Sim — um campo `text` obrigatório "Título do método" com `help_text` curto.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Carga única habilita todas as demonstrações (Priority: P1)

Quem for apresentar o sistema sobe a aplicação, executa **um** comando de carga
(`seed_all`) e, sem nenhum passo manual adicional, consegue percorrer todas as
demonstrações da pasta `demos/` com dados reais vindos da API.

**Why this priority**: É o objetivo central declarado ("que seja simples"). Sem isso,
a apresentação exige preparação manual frágil e propensa a falhar ao vivo.

**Independent Test**: Em um banco limpo, rodar a carga mestre e abrir cada
demonstração do catálogo; cada uma deve carregar seus dados e permitir o fluxo
principal sem erro de "dados ausentes / rode o seed".

**Acceptance Scenarios**:

1. **Given** um banco recém-migrado e vazio, **When** o operador executa a carga
   mestre `seed_all`, **Then** a carga conclui sem erro e imprime as credenciais e os
   links das demonstrações.
2. **Given** a carga mestre concluída, **When** o operador abre o catálogo de demos e
   entra em cada demonstração listada (editor de formulário + IA, submissão +
   pré-avaliação, triagem + feedback, observabilidade de IA, e as ferramentas de
   apoio), **Then** cada página autentica, encontra seus dados e exibe o estado
   esperado para a demonstração.
3. **Given** a carga mestre já executada uma vez, **When** o operador a executa
   novamente, **Then** a carga é idempotente (não duplica processos nem usuários) e
   termina no mesmo estado.
4. **Given** a demonstração de triagem, **When** o avaliador abre a fila, **Then**
   existe pelo menos um processo em triagem com pré-avaliação de IA executada para
   inspecionar.

---

### User Story 2 - Demonstrações com padrão visual e narrativo consistente (Priority: P2)

Uma pessoa sem conhecimento técnico assiste à demonstração (ao vivo ou em vídeo) e
percebe um produto único e acabado: todas as telas compartilham identidade visual,
tom e estrutura; o texto é enxuto; os rótulos da interface estão em português (com
termo em inglês só quando não há equivalente corrente); cada demo deixa claro, em
poucas palavras, o que está sendo mostrado e qual o próximo passo. As 6 páginas são
reescritas para seguir o padrão comum.

**Why this priority**: A consistência é o que diferencia "protótipo de engenharia" de
"produto apresentável". Depende da massa de dados da User Story 1 para ser exercida.

**Independent Test**: Abrir as seis páginas em sequência e verificar contra um
checklist de padrão compartilhado (cabeçalho, paleta, tipografia, densidade de texto,
rótulos em português, indicador de status da API, chamada de ação).

**Acceptance Scenarios**:

1. **Given** o catálogo de demos, **When** um observador o abre, **Then** ele lista
   todas as demonstrações existentes com uma descrição curta de cada uma e nenhum link
   quebrado (em particular, nenhuma referência ao `DESIGN.md` removido).
2. **Given** qualquer página de demonstração, **When** ela é aberta, **Then** ela
   segue o mesmo cabeçalho, paleta, tipografia e componente de status da API das
   demais.
3. **Given** qualquer página de demonstração, **When** um leitor a percorre, **Then**
   o conteúdo textual é curto e objetivo e os rótulos da interface estão em português
   (termo em inglês apenas quando não há equivalente em português de uso corrente).
4. **Given** todas as instruções de "como carregar os dados" espalhadas pelas demos,
   **When** comparadas entre si, **Then** todas citam exatamente o mesmo comando de
   carga.
5. **Given** o `DESIGN.md` foi removido, **When** a feature é concluída, **Then** ele
   não é recriado; qualquer diretriz de padrão necessária vive de outra forma
   acordada.

---

### User Story 3 - Formulários de submissão redesenhados por propósito de demo (Priority: P2)

Ao instanciar cada um dos cinco processos padrão, o formulário da seção inicial reflete
o papel daquele processo na demonstração:

- **Processos 1 a 3** (`pre_validated_method`, `scope_extension`, `me_too_validation`):
  formulário mínimo — **um único campo**, não vazio, só para haver algo na tela.
- **Processo 4** (`validated_method_dossier`): formulário curto que exemplifica, de
  forma rasa, o uso da IA do sistema — por exemplo, ajudar a encontrar/atualizar a
  terminologia de um conceito para termos mais modernos.
- **Processo 5** (`proof_of_concept`): o **Formulário Preliminar (FP)** real do
  BraCVAM, convertido para a estrutura de campos do sistema, com os itens não
  suportados registrados como pendência.

**Why this priority**: É a parte visível do "estado base" que o público vai realmente
ler na tela. Pode ser entregue independentemente das demos, mas precisa estar alinhada
com os seeds.

**Independent Test**: Instanciar cada processo e abrir o formulário da atividade de
submissão; verificar contagem de campos, obrigatoriedade e rótulos contra esta
especificação.

**Acceptance Scenarios**:

1. **Given** os processos 1, 2 e 3, **When** o formulário de submissão de cada um é
   aberto, **Then** ele contém exatamente um campo `text` obrigatório de título do
   método, com rótulo em português e `help_text` curto que evite a aparência de tela
   vazia.
2. **Given** o processo 4, **When** o formulário de submissão é aberto, **Then** ele
   contém poucos campos (não mais que o necessário para a narrativa), com pelo menos um
   campo com avaliação por IA habilitada e instruções de contexto voltadas a
   "modernizar a terminologia de um conceito".
3. **Given** o processo 5, **When** o formulário de submissão é aberto, **Then** ele
   reproduz a estrutura e o agrupamento por seções do FP do BraCVAM, com todas as 9
   seções presentes.
4. **Given** o processo 5, **When** um elemento do FP não pode ser representado
   nativamente, **Then** ele aparece aproximado pelo tipo suportado mais próximo e a
   aproximação está listada nas pendências desta feature (nenhum elemento é omitido).
5. **Given** qualquer alteração nos formulários de submissão, **When** `seed_all` é
   executado, **Then** a carga continua concluindo sem erro (os seeds foram ajustados
   aos novos campos na mesma entrega).
6. **Given** o formulário de parecer de triagem (`triage_review_v1`), **When** os
   formulários de submissão são refatorados, **Then** ele permanece inalterado.

---

### Edge Cases

- **Seed sobre banco parcialmente carregado**: a carga mestre deve convergir para o
  estado alvo sem duplicar nem falhar quando alguns usuários/processos já existem.
- **Demo aberta antes do seed**: cada página deve exibir uma mensagem clara e única
  ("execute a carga de dados") em vez de erro cru — e todas devem citar o mesmo
  comando.
- **Processo 5 com campos longos**: limites de palavras do FP (ex.: "máx. 150
  palavras") não são exatamente aplicáveis pelos mecanismos de validação atuais; o
  comportamento esperado (orientar via texto de ajuda vs. bloquear) precisa estar
  definido.
- **Campo único dos processos 1-3 marcado como obrigatório**: a submissão de
  demonstração ainda precisa ser possível preenchendo apenas esse campo.
- **Seeds órfãos fora da carga mestre** (ex.: `seed_form_ai_demo.py`): removidos por
  esta feature, pois dependem de campos que deixam de existir e são redundantes com a
  carga mestre.

## Requirements *(mandatory)*

### Functional Requirements

#### Carga de dados (seed)

- **FR-001**: A carga mestre `seed_all` MUST, a partir de um banco migrado e vazio,
  provisionar toda a massa de dados necessária para percorrer cada demonstração
  listada no catálogo `demos/`, sem passos manuais adicionais.
- **FR-002**: A carga mestre MUST ser idempotente: reexecutá-la não cria processos,
  usuários ou avaliações duplicados e converge para o mesmo estado.
- **FR-003**: A carga mestre MUST deixar pelo menos um processo em triagem com uma
  pré-avaliação de IA já executada, para as demonstrações de triagem e de
  observabilidade de IA.
- **FR-004**: Os scripts de seed que compõem a carga mestre MUST ser atualizados na
  mesma entrega para permanecerem compatíveis com os formulários de submissão
  redesenhados (nenhum seed pode referenciar um campo que deixou de existir).
- **FR-005**: A saída final da carga mestre MUST informar as contas de teste (com
  perfil) e os links das demonstrações.
- **FR-006**: Os scripts de seed órfãos que não fazem parte da carga mestre `seed_all`
  (ex.: `seed_form_ai_demo.py`) MUST ser removidos do repositório; após a entrega,
  todo script de seed remanescente pertence à carga mestre e permanece funcional.

#### Demonstrações (demos)

- **FR-007**: O catálogo `demos/index.html` MUST listar todas as demonstrações
  existentes na pasta `demos/`, cada uma com um título e uma descrição curta, e MUST
  NOT conter links quebrados.
- **FR-008**: Todas as referências ao `DESIGN.md` removido MUST ser eliminadas do
  catálogo e das páginas; o `DESIGN.md` MUST NOT ser recriado.
- **FR-009**: As 6 páginas de demonstração MUST ser reescritas para seguir um padrão
  visual comum — cabeçalho, paleta, tipografia, espaçamento, estilo de botões e um
  componente comum de indicação do status da API — de modo que aparentem um único
  produto.
- **FR-010**: O conteúdo textual das páginas de demonstração MUST ser enxuto —
  priorizando rótulos, passos curtos e chamadas de ação em vez de parágrafos
  explicativos longos.
- **FR-011**: Os rótulos e textos exibidos na interface das demonstrações MUST estar
  em português; um termo em inglês só é aceitável quando não houver equivalente em
  português de uso corrente (ex.: termo técnico consagrado).
- **FR-012**: Cada página de demonstração MUST comunicar, em poucas palavras, o que
  está sendo demonstrado e qual é a ação seguinte.
- **FR-013**: Todas as instruções de "como carregar os dados" presentes nas demos MUST
  citar exatamente o mesmo comando de carga.
- **FR-014**: Quando uma demonstração é aberta sem a massa de dados carregada, ela
  MUST exibir uma mensagem única e orientadora (não um erro cru).
- **FR-015**: As páginas de demonstração MUST permanecer totalmente desacopladas de
  `src/` e operar exclusivamente contra a API real (sem endpoints facilitadores, sem
  simulação no frontend).

#### Formulários de submissão (`templates_data`)

- **FR-016**: A refatoração MUST alterar apenas o formulário da atividade de submissão
  (seção inicial) de cada um dos cinco templates de processo; o formulário
  `triage_review_v1` (parecer de triagem) MUST permanecer inalterado.
- **FR-017**: Os formulários de submissão dos processos `pre_validated_method`,
  `scope_extension` e `me_too_validation` MUST conter exatamente um campo cada: um
  `text` obrigatório de título do método (rótulo em português, com `help_text` curto),
  suficiente para uma tela não vazia e uma submissão de demonstração válida.
- **FR-018**: O formulário de submissão do processo `validated_method_dossier` MUST
  conter um conjunto mínimo de campos que exemplifique de forma rasa o uso da IA do
  sistema, com pelo menos um campo com avaliação por IA habilitada e instruções de
  contexto orientadas a modernizar/encontrar a terminologia de um conceito.
- **FR-019**: O formulário de submissão do processo `proof_of_concept` MUST reproduzir
  o Formulário Preliminar (FP) do BraCVAM com rótulos em português, preservando o
  agrupamento em seções (1. Informações Gerais; 2. Informações do Método de Teste; 3.
  Resumo; 4. Otimização do Protocolo; 5. Confiabilidade; 6. Capacidade Preditiva; 7.
  Referências; 8. Confidencialidade; 9. Solicitação ao BraCVAM).
- **FR-020**: Cada elemento do FP que não puder ser representado nativamente MUST ser
  aproximado pelo tipo de campo suportado mais próximo (múltipla escolha → vários
  campos `boolean` ou um `textarea`; "se sim, especifique" → `textarea` sempre visível;
  tabela ou lista repetível → um `textarea`) e agrupado por `section`; toda aproximação
  MUST ser registrada como pendência nesta feature, com a razão. Nenhum elemento do FP
  é silenciosamente omitido.
- **FR-021**: Os formulários redesenhados MUST usar somente tipos de campo e chaves de
  configuração já suportados pelo motor de formulários (`text`, `textarea`, `integer`,
  `float`, `boolean`, `date`, `select`, `file_upload`; `validation_rules`, `section`,
  `options`, `ai_*`), conforme a especificação de sintaxe YAML do projeto.
- **FR-022**: Após a refatoração, instanciar cada processo e submeter seu formulário
  de demonstração MUST continuar funcionando de ponta a ponta pela API real.
- **FR-023**: As chaves semânticas dos cinco templates de processo e a estrutura de
  fases/atividades MUST permanecer inalteradas.

### Key Entities *(include if feature involves data)*

- **Template de Processo**: um dos cinco processos canônicos da Fase 1 do BraCVAM
  (`pre_validated_method`, `scope_extension`, `me_too_validation`,
  `validated_method_dossier`, `proof_of_concept`). Contém fases, atividades e
  formulários declarados em YAML.
- **Formulário de Submissão**: o formulário vinculado à atividade `proposal_submission`
  de cada template — o único artefato de formulário alterado por esta feature.
- **Formulário de Parecer de Triagem** (`triage_review_v1`): compartilhado pelos cinco
  templates; fora do escopo de alteração.
- **Campo de Formulário**: unidade do formulário, com tipo, obrigatoriedade, seção,
  texto de ajuda e configuração opcional de avaliação por IA.
- **Massa de Dados de Demonstração**: usuários e perfis RBAC, os cinco processos
  instanciados, um processo em triagem e uma definição de avaliação de IA publicada e
  associada a um campo — tudo produzido pela carga mestre.
- **Página de Demonstração**: página estática em `demos/` que consome a API real; seis
  no total (editor de formulário + IA, submissão + pré-avaliação, triagem + feedback,
  observabilidade de IA, gestão de usuários/RBAC, índice operacional).
- **Catálogo de Demonstrações** (`demos/index.html`): ponto de entrada que lista e
  descreve todas as páginas de demonstração.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A partir de um banco migrado e vazio, um único comando de carga deixa
  100% das demonstrações do catálogo operáveis, sem nenhum passo manual adicional.
- **SC-002**: Um operador consegue ir do banco vazio à primeira demonstração aberta e
  funcional em menos de 5 minutos.
- **SC-003**: Reexecutar a carga mestre duas vezes seguidas resulta em contagens
  idênticas de usuários, processos e avaliações (zero duplicação).
- **SC-004**: As seis páginas de demonstração passam por um checklist de padrão
  compartilhado com 100% de conformidade nos itens de cabeçalho, paleta, tipografia,
  status da API, rótulos em português e densidade de texto.
- **SC-005**: Zero links quebrados no catálogo de demos e zero referências ao
  `DESIGN.md` em toda a pasta `demos/`.
- **SC-006**: Todas as instruções de carga de dados nas demos citam um único comando
  idêntico (verificável por busca textual).
- **SC-007**: Os formulários dos processos 1-3 têm exatamente um campo cada; o do
  processo 4 tem no máximo os campos necessários para a narrativa de IA; o do processo
  5 apresenta todas as 9 seções do FP.
- **SC-008**: 100% dos elementos do FP aproximados (não representados nativamente)
  estão listados como pendência com justificativa.
- **SC-009**: `poe format`, `poe lint` e `poe test` permanecem verdes após a entrega.
- **SC-010**: Após a entrega, todo script de seed do repositório pertence à carga
  mestre `seed_all` e executa sem erro; zero scripts de seed órfãos.

## Pendências e Lacunas Conhecidas (Formulário Preliminar do BraCVAM)

Elementos do FP que os tipos de campo e regras de validação atuais **não** representam
diretamente. Conforme decidido nas Clarifications, cada um é **aproximado** pelo tipo
suportado mais próximo (nunca omitido) e agrupado por `section`; o mapeamento
campo a campo vai para o `plan.md`:

- **Grupos de checkbox / múltipla escolha** (item 3.1 "aborda: saúde humana / efeitos
  ambientais / outros"; item 4.2 controles positivo/negativo/referência): o tipo
  `select` só permite escolha única; não há tipo "múltipla seleção".
- **Sub-campos condicionais** ("se sim, especifique…"): não há visibilidade condicional
  de campo; cada "especifique" vira um campo de texto sempre visível.
- **Tabela / grupo repetível** (item 8: até 20 linhas de "item confidencial" +
  "explicação"; item 7: lista de até 10 referências): não há tipo de campo de tabela
  nem de lista repetível; provável aproximação por um único `textarea`.
- **Limite por número de palavras** ("máx. 150 palavras", "máx. 100 palavras por
  parágrafo"): a validação suporta `min_length` (caracteres), não contagem de palavras
  nem `max_length`.
- **Pares título + valor extensos** (blocos de contato do proponente e do contato
  adicional): serão achatados em vários campos `text` agrupados por `section`,
  perdendo a semântica de "repetir o bloco para um segundo contato".
- **Marcação de confidencialidade por parágrafo** (item 8): sem vínculo estrutural
  entre um parágrafo do formulário e sua marcação de confidencial.

## Assumptions

- O motor de formulários e a sintaxe YAML permanecem como documentado em
  `src/pivma/templates_data/README.md`; esta feature não adiciona tipos de campo novos.
- "Demonstração chamada de vídeo" é interpretada como uma demonstração guiada, de tom
  sóbrio e para público não técnico, adequada tanto para condução ao vivo quanto para
  gravação — não a produção de um arquivo de vídeo.
- As seis páginas atuais em `demos/` (`forms`, `submission`, `triage`, `ai-pipeline`,
  `users`, `operational-index`) são o conjunto a padronizar; nenhuma demo nova é criada
  nesta feature.
- O comando de carga canônico é `uv run python -m scripts.seeds.seed_all` (a paridade
  com Poetry é mantida); as demos passam a citar esse comando.
- Os cinco processos permanecem restritos à Fase 1 (Submissão e Triagem).
- O conteúdo do FP fornecido na solicitação é a fonte de verdade para o processo 5.
- Todos os rótulos dos formulários de submissão (1 a 5) e da interface das demos são em
  português; um termo em inglês só aparece quando não há equivalente em português de
  uso corrente.
- As credenciais de teste atuais (`admin` / `proponent_user` / `triage_evaluator`) e
  seus perfis permanecem válidos.
- A carga mestre continua usando o provedor de IA determinístico ("fake") para não
  depender de chave externa durante o seed.

## Dependencies

- Motor de processos e formulários (`pivma.core.process_engine`,
  `pivma.bootstrap_process_templates`).
- Serviços de avaliação e pré-avaliação por IA (Specs 010/013).
- Semântica de triagem BraCVAM e autorização (Spec 014).
- API real em execução para exercitar as demonstrações (critério de conclusão do
  `AGENTS.md`).

## Out of Scope

- Introdução de novos tipos de campo, validação por contagem de palavras ou campos
  condicionais/repetíveis no motor de formulários.
- Alterações no formulário de parecer de triagem (`triage_review_v1`).
- Alterações nas fases/atividades ou nas chaves semânticas dos processos.
- Fases posteriores do ciclo BraCVAM além da Fase 1.
- Redesign da aplicação real (`src/`) ou de suas respostas de API.
- Produção de um arquivo de vídeo da demonstração.

# Feature Specification: Terminologia dos tipos e código da submissão

**Feature Branch**: `feat/043-submission-types-and-code`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Ajustes pedidos pelo BraCVAM na área de
submissões. Renomear e reordenar os quatro tipos de submissão com os nomes e
descrições da tabela, mantendo as chaves técnicas, e fazer
GET /processes/templates devolver os tipos na ordem definida; remover por
completo o tipo Prova de Conceito e seu formulário; gerar o código da
submissão no formato sequencial VAL-<ano>-<sequencial> por ano, único sob
concorrência e sem consumir número em criação que falha. Fora de escopo:
título único, explicação do botão Enviar para análise, Formulário Preliminar
em toda submissão, mudanças no frontend. Preview é descartável e a produção
começa vazia: sem migração de dados antigos."

## Contexto

- **CONFIRMADO, documento do BraCVAM** ("Sugestões de ajustes no sistema
  PiVMA", outubro de 2026): a seção 1 pede os tipos com a terminologia do
  OECD GD 34, sem inglês na tela, numa ordem definida, e a remoção da Prova
  de Conceito. A seção 2.1, item 3, pergunta como o código da submissão é
  gerado.
- **CONFIRMADO, fonte oficial**: o Plano de Trabalho não define os tipos de
  submissão. A seção 3.2 ("crCode") só exige um identificador único.
- **CONFIRMADO, implementação atual**: cada tipo é um template de processo
  declarado em `src/pivma/templates_data/`. O bootstrap regrava nome e
  descrição a cada deploy e desativa, com soft delete, os templates e
  formulários cujo YAML sumiu. `GET /processes/templates` ordena por nome e
  chave.
- **CONFIRMADO, implementação atual**: o código é `VAL-<ano>-<16 hex
  aleatórios>`, gerado na criação do processo e protegido por restrição de
  unicidade no banco.
- **CONFIRMADO, implementação atual**: a Prova de Conceito é o único tipo com
  o Formulário Preliminar do BraCVAM (Spec 015, FR-019). Testes e o manual a
  usam como exemplo.

## Clarifications

### Session 2026-10-24 (usuário)

Decisões copiadas de `docs/observacoes-e-pendencias.md`, seção
"Terminologia dos tipos e código da submissão".

- **Nomes e descrições**: os tipos passam a ser, nesta ordem:

  | Ordem | Chave | Nome | Descrição |
  |---|---|---|---|
  | 1 | `pre_validated_method` | Método Novo | Método em desenvolvimento ou já desenvolvido, cujo processo de validação ainda não foi executado. |
  | 2 | `validated_method_dossier` | Método Novo – Dossiê Completo | Método novo já desenvolvido, com protocolo estabelecido e processo de validação concluído, cujo dossiê está disponível para avaliação por pares. |
  | 3 | `scope_extension` | Extensão do Domínio de Aplicação | Proposta de ampliação do domínio de aplicação de um método já validado, incluindo uma nova finalidade de uso ou aplicação regulatória. |
  | 4 | `me_too_validation` | Método Similar | Método de ensaio estrutural e funcionalmente semelhante a um método de referência já validado e aceito, podendo ser candidato a um processo de validação baseado em padrões de desempenho (performance standards). |

  A expressão "Fitness for Purpose Validation" sai da descrição da Extensão.
- **Chaves técnicas**: as chaves dos tipos e dos formulários não mudam. O
  frontend e os testes dependem delas. Esconder as chaves da tela cabe ao
  frontend.
- **Ordem**: `GET /processes/templates` devolve os tipos na ordem da tabela.
  O template de processo declara a própria ordem de exibição, e a lista deixa
  de ordenar pelo nome. A ordem é obrigatória no YAML: o bootstrap recusa o
  arquivo sem ela.
- **Prova de Conceito**: sai por completo: o YAML, o formulário
  `submission_proof_of_concept_v1`, os testes que cobrem só esse tipo e as
  menções no manual e no `templates_data/README.md`. A Spec 015 fica como
  está, por ser histórico. O mapeamento do Formulário Preliminar continua em
  `specs/015-first-deploy-baseline/data-model.md` e no git.
- **Código da submissão**: formato `VAL-<ano>-<sequencial>`, como
  `VAL-2026-0001`. A sequência recomeça em 1 a cada ano e usa no mínimo
  quatro dígitos, com zeros à esquerda; acima de 9999 o número só cresce
  (`VAL-2026-10000`). O ano é o da criação no horário de Brasília
  (`America/Sao_Paulo`). Duas criações
  simultâneas nunca recebem o mesmo número, e uma criação que falha não
  consome número.
- **Dados existentes**: o preview só tem dados de teste e a produção começa
  vazia. Não há migração dos códigos antigos nem tratamento de processos
  abertos da Prova de Conceito.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Proponente escolhe entre os quatro tipos com os nomes novos (Priority: P1)

O proponente abre a tela de nova submissão e vê quatro tipos, na ordem
pedida pelo BraCVAM, com nomes e descrições em português alinhados ao OECD
GD 34. A Prova de Conceito não aparece. Ele escolhe um tipo e cria a
submissão como antes.

**Why this priority**: é o primeiro contato do proponente com o sistema e o
ponto que o BraCVAM revisou primeiro. Sem ele, a terminologia oficial não
chega à tela.

**Independent Test**: com os templates carregados, um usuário autenticado
lista os tipos e recebe os quatro, na ordem e com os textos da tabela; a
criação de processo com cada chave mantida funciona, e com
`proof_of_concept` falha.

**Acceptance Scenarios**:

1. **Given** os templates carregados pelo bootstrap, **When** um usuário
   autenticado lista os tipos de submissão, **Then** recebe exatamente
   quatro, na ordem Método Novo, Método Novo – Dossiê Completo, Extensão do
   Domínio de Aplicação e Método Similar.
2. **Given** a lista de tipos, **When** o usuário lê nome e descrição de cada
   um, **Then** os textos são os da tabela das Clarifications e nenhum
   contém "Fitness".
3. **Given** a lista de tipos, **When** o usuário procura a Prova de
   Conceito, **Then** ela não aparece e o total informado na paginação é 4.
4. **Given** um proponente, **When** ele cria uma submissão com uma das
   quatro chaves mantidas, **Then** a criação funciona como antes.
5. **Given** um proponente, **When** ele tenta criar uma submissão com a
   chave `proof_of_concept`, **Then** recebe 404 com "Template não
   encontrado ou inativo." e nenhum processo é criado.
6. **Given** um banco em que a Prova de Conceito já tinha sido carregada,
   **When** o bootstrap roda de novo, **Then** o tipo e o formulário
   `submission_proof_of_concept_v1` ficam desativados e fora das listas.

---

### User Story 2 - Submissão recebe um código sequencial legível (Priority: P2)

Ao criar uma submissão, o proponente recebe um código como `VAL-2026-0001`,
que indica o ano e um número sequencial. O BraCVAM e o proponente conseguem
citar o código em conversas e e-mails.

**Why this priority**: responde à pergunta do BraCVAM sobre o código. O
código atual funciona, então a mudança vem depois da terminologia.

**Independent Test**: criar submissões em sequência, em paralelo, com falha
no meio e em anos diferentes, e conferir os códigos gerados.

**Acceptance Scenarios**:

1. **Given** nenhuma submissão criada no ano corrente, **When** o proponente
   cria uma submissão, **Then** o código é `VAL-<ano>-0001`.
2. **Given** a submissão `VAL-<ano>-0001`, **When** outra submissão é criada
   no mesmo ano, **Then** o código é `VAL-<ano>-0002`.
3. **Given** duas criações simultâneas no mesmo ano, **When** ambas
   concluem, **Then** recebem números distintos e consecutivos.
4. **Given** uma criação que falha depois de reservar o número, **When** a
   próxima criação conclui, **Then** ela recebe o número que a criação
   falha teria usado.
5. **Given** a última submissão do ano anterior com qualquer número, **When**
   a primeira submissão do novo ano é criada, **Then** o código é
   `VAL-<novo ano>-0001`.
6. **Given** a submissão de número 9999 no ano, **When** a próxima é criada,
   **Then** o código é `VAL-<ano>-10000`.
7. **Given** 31 de dezembro às 22h no horário de Brasília (1h de 1º de
   janeiro em UTC), **When** uma submissão é criada, **Then** o código usa
   o ano que está terminando.

### Edge Cases

- YAML de tipo sem ordem de exibição: o bootstrap confere a ordem de todos
  os YAMLs antes de gravar qualquer um. Se um deles não tem ordem, o
  bootstrap para com erro que cita a chave do tipo e não grava nenhum
  template.
- Template de processo criado direto no banco, sem YAML, como nos testes:
  aparece depois dos tipos com ordem, sem quebrar a lista.
- Dois tipos com a mesma ordem de exibição: a lista desempata pela chave,
  para que a paginação seja estável.
- Um processo criado antes desta feature com código no formato antigo
  continua válido; a sequência nova não depende dele.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE apresentar os quatro tipos de submissão com os
  nomes e as descrições da tabela das Clarifications.
- **FR-001a**: O formulário de submissão de cada tipo DEVE se chamar
  "Formulário de Submissão - <nome do tipo>", com o nome novo.
- **FR-002**: O sistema DEVE manter as chaves técnicas dos tipos
  (`pre_validated_method`, `validated_method_dossier`, `scope_extension`,
  `me_too_validation`) e dos seus formulários.
- **FR-003**: A listagem de tipos de submissão DEVE devolver os tipos na
  ordem de exibição declarada por cada tipo, com desempate pela chave, e
  informar essa ordenação no campo de ordenação aplicada da resposta.
- **FR-003a**: O carregamento dos templates DEVE recusar um YAML de tipo que
  não declare a ordem de exibição como inteiro maior ou igual a 1. A
  recusa acontece antes de gravar qualquer template e interrompe o
  carregamento.
- **FR-004**: O sistema NÃO DEVE oferecer o tipo Prova de Conceito nem o
  formulário `submission_proof_of_concept_v1`. Ao carregar os templates, o
  sistema DEVE desativar esse tipo e esse formulário onde já existirem.
- **FR-005**: A criação de submissão com a chave `proof_of_concept` DEVE
  falhar com 404, sem criar processo.
- **FR-006**: O sistema DEVE gerar o código da submissão no formato
  `VAL-<ano>-<sequencial>`, com o ano da criação no horário de Brasília e
  o sequencial com
  no mínimo quatro dígitos, completados com zeros à esquerda.
- **FR-007**: O sequencial DEVE começar em 1 em cada ano e crescer de 1 em 1.
- **FR-008**: Criações simultâneas NÃO DEVEM receber o mesmo código.
- **FR-009**: Uma criação de submissão que falha NÃO DEVE consumir número da
  sequência.
- **FR-010**: O repositório NÃO DEVE manter testes, exemplos ou documentação
  do estado atual que dependam da Prova de Conceito. A Spec 015 fica intacta
  como histórico.
- **FR-011**: O manual DEVE descrever os tipos com os nomes novos, a ordem da
  listagem e o formato do código.

### Key Entities

- **Tipo de submissão** (template de processo): ganha a ordem de exibição,
  um inteiro declarado no YAML de cada tipo. Nome e descrição mudam.
- **Sequência anual de códigos**: o último número usado em cada ano. Serve
  só para gerar o próximo código.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A tela de nova submissão mostra 4 tipos, na ordem pedida pelo
  BraCVAM, sem nenhum termo em inglês nos nomes.
- **SC-002**: Nenhuma tentativa de criar submissão do tipo Prova de Conceito
  é aceita.
- **SC-003**: Em 100% das criações de submissão de um ano, os códigos são
  distintos, inclusive com criações simultâneas. O número segue a ordem em
  que o banco reserva cada código, que pode diferir da ordem em que as
  requisições chegaram.
- **SC-004**: Até a 9.999ª submissão do ano, o código tem 13 caracteres
  (`VAL-2026-0001`), contra 25 no formato anterior.
- **SC-005**: Nenhuma busca no repositório por `proof_of_concept` encontra
  código, teste ou documentação do estado atual que dependa da Prova de
  Conceito. Só aparecem as specs históricas e os testes que provam a
  ausência dela (US1, cenários 5 e 6).

## Assumptions

- A listagem de tipos continua aberta a qualquer usuário autenticado, como
  hoje. Nenhuma permissão muda.
- O frontend mostra os tipos na ordem em que a API os devolve. Esconder as
  chaves técnicas da tela é trabalho do frontend, fora deste repositório.
- Os formulários dos quatro tipos mantidos não mudam nesta feature.
- Fora de escopo: título único, explicação do botão "Enviar para análise",
  Formulário Preliminar em toda submissão e qualquer mudança no frontend.

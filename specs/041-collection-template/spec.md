# Feature Specification: Template de coleta de dados

**Feature Branch**: `feat/041-collection-template`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "We will implement the issue #26 assigned to me.
Claude already made an analises of the code and doc, we should take this into
account. We should implement this issue with the lowest complexity possible,
but do not create gaps and technical debts."

- #26 ([E2-05] Definição do Template de Coleta de Dados — novo domínio): o
  construtor de colunas (rótulo, chave técnica, tipo, obrigatoriedade,
  opções), os parâmetros de experimentos e réplicas e o arquivo-modelo em CSV
  e Excel.
- A #30 (upload de resultados) consome o contrato definido aqui.

## Contexto

- **CONFIRMADO, fonte oficial**: o Plano de Trabalho não tem RF específico
  para o template de coleta. O mais próximo é o RF036 (configuração dinâmica
  de formulários).
- **CONFIRMADO, decisão da equipe**: as decisões de 2026-10-09 em
  [`docs/observacoes-e-pendencias.md`](../../docs/observacoes-e-pendencias.md)
  (seção "Template de coleta de dados") complementam a issue e prevalecem
  sobre o guia do protótipo, que está descontinuado. A regra geral delas é
  implementar com a menor complexidade que cumpra os critérios de aceite.
- **CONFIRMADO, implementação atual**: a definição das amostras (Spec 031)
  conclui uma vez e fica congelada. Não existe operação que a reabra; a
  reabertura da Spec 036 só vale para atividades por laboratório. A Etapa 3
  (`phase_3_validation_execution`, Spec 040) depende dessa conclusão.
- **CONFIRMADO, implementação atual**: a criação de processo aceita qualquer
  pessoa autenticada, que vira proponente do processo. A trilha de auditoria
  de eventos exige um processo, então ela não registra mudanças de catálogo.
  Os catálogos atuais guardam quem criou, alterou e excluiu cada registro e
  quando.

## Clarifications

### Session 2026-10-09 (decisões da equipe, `docs/observacoes-e-pendencias.md`)

- Q: O template de coleta reaproveita os formulários dinâmicos? → A: Não.
  Ele tem estrutura própria: um template (nome, descrição, mínimo de
  experimentos, mínimo de réplicas) e suas colunas (rótulo, chave técnica,
  tipo, obrigatoriedade, opções, posição), ambos com autoria e datas de
  criação, alteração e exclusão (decisão 1).
- Q: Quais tipos de coluna existem? → A: Exatamente `text`, `integer`,
  `decimal`, `date` e `select`. `select` exige opções não vazias; os outros
  tipos rejeitam opções (decisão 2).
- Q: O arquivo traz colunas fixas? → A: Sim. Toda saída começa com
  `codigo_amostra`, `experimento` e `replica`, nessa ordem. Elas são fixas,
  não pertencem ao cadastro do template e suas chaves são reservadas:
  criar coluna com uma delas é recusado, como chave duplicada. Laboratório,
  operador e datas não entram; o laboratório vem da autenticação (decisão 3).
- Q: Colunas derivadas e a flag "permitir ensaios fracassados" entram? → A:
  Não. Nenhuma fonte define a fórmula nem a semântica, e a #30 é quem as
  consumiria (decisão 4).
- Q: Quando a "Etapa 3 começa"? → A: Quando a definição das amostras do
  processo fica concluída. A Etapa 3 é a fase `phase_3_validation_execution`
  (decisão 5).
- Q: O template pertence a um processo? → A: Não. Ele forma um catálogo
  global, criado antes e escolhido na criação do processo, por um campo
  opcional. O processo guarda o vínculo, que pode ficar vazio, e nenhuma
  operação o troca depois (decisão 6).
- Q: Como funciona o travamento estrutural? → A: O template fica travado se
  algum processo vinculado a ele tem a definição das amostras concluída. O
  sistema calcula o estado na hora, sem marcador armazenado. Um template
  travado continua selecionável por processos novos (decisão 6).
- Q: Quem gerencia o catálogo? → A: Uma permissão nova, nos moldes da
  permissão de gestão de formulários, concedida ao Admin e à BraCVAM
  (decisão 6).
- Q: O protótipo vale como fonte? → A: Não, está descontinuado (decisão 7).
- Q: Qual formato Excel? → A: `.xlsx`, gerado com uma biblioteca que também
  lê o formato, porque a #30 vai ler o arquivo preenchido (decisão 8).
- Q: Como são experimentos e réplicas? → A: Mínimos, inteiros maiores ou
  iguais a 1 (decisão 9).
- Q: Como é a posição da coluna? → A: Inteiro maior ou igual a 1, único
  dentro do template. Sem posição informada, a coluna vai para o fim.
  Reordenar fica fora de escopo (decisão menor).
- Q: Qual o formato da chave técnica? → A: Casa com `^[a-z][a-z0-9_]{0,63}$`
  e é única dentro do template (decisão menor).
- Q: Como é o arquivo-modelo? → A: Só o cabeçalho, em CSV e em Excel. O CSV
  usa UTF-8 com BOM e separador `;`. O Excel não traz validação de lista
  (decisão menor).
- Q: Como nomear? → A: Template de coleta (`CollectionTemplate`), tabelas
  `collection_templates` e `collection_template_columns`, rota
  `/collection-templates`. O arquivo baixado é o arquivo-modelo (glossário).

### Session 2026-10-09 (lacunas das decisões)

- Q: Quem pode informar o template de coleta ao criar um processo? → A: Só
  quem tem a permissão de gestão do catálogo. Quem não tem e envia o campo
  recebe recusa por falta de permissão, e nenhum processo é criado. Sem o
  campo, a criação segue aberta a qualquer pessoa autenticada (usuário,
  2026-10-09).
- Q: Quem pode listar e consultar o catálogo e baixar o arquivo-modelo? →
  A: Só quem tem a permissão de gestão do catálogo. O acesso do laboratório
  ao arquivo-modelo do seu processo fica para a #30 (usuário, 2026-10-09).
- Q: O cabeçalho do arquivo-modelo traz a chave técnica ou o rótulo? → A: A
  chave técnica, estável e fácil de interpretar pela #30. O rótulo aparece na
  consulta do template (usuário, 2026-10-09).

## User Scenarios & Testing *(mandatory)*

Personas: **Beatriz**, da BraCVAM, monta o catálogo de templates de coleta;
**Paulo**, proponente, cria o processo de validação.

### User Story 1 - Montar um template de coleta e baixar o arquivo-modelo (Priority: P1)

Beatriz cria o template "Ensaio de citotoxicidade" com descrição, mínimo de 3
experimentos e 2 réplicas. Ela adiciona seis colunas: `viabilidade`
(decimal, obrigatória), `contagem_celulas` (inteiro, obrigatória),
`data_leitura` (data, obrigatória), `observacao` (texto, opcional),
`resultado` (seleção com "positivo", "negativo" e "inconclusivo",
obrigatória) e `lote_reagente` (texto, opcional). Ela baixa o arquivo-modelo
em CSV e em Excel e confere o cabeçalho: as três colunas fixas seguidas das
seis colunas na ordem das posições.

**Why this priority**: é o núcleo da issue. A #30 depende desse contrato
para receber os resultados.

**Independent Test**: criar o template com as seis colunas de tipos mistos
(cenário de teste da issue), baixar os dois formatos e comparar o cabeçalho
com a lista esperada.

**Acceptance Scenarios**:

1. **Given** Beatriz com a permissão de gestão do catálogo, **When** ela cria
   um template com nome, descrição, mínimo de experimentos e de réplicas
   válidos, **Then** o template é salvo sem colunas e destravado.
2. **Given** o template criado, **When** Beatriz adiciona as seis colunas sem
   informar posição, **Then** cada coluna recebe a posição seguinte à maior
   existente (1 a 6).
3. **Given** o template com as seis colunas, **When** Beatriz consulta o
   template, **Then** recebe nome, descrição, mínimos, estado de travamento
   e as colunas ordenadas por posição, cada uma com rótulo, chave técnica,
   tipo, obrigatoriedade, opções e posição.
4. **Given** o template com as seis colunas, **When** Beatriz baixa o CSV,
   **Then** recebe um arquivo UTF-8 com BOM, separador `;`, uma única linha
   de cabeçalho com `codigo_amostra`, `experimento`, `replica` e as seis
   colunas na ordem das posições, e um nome de arquivo sugerido.
5. **Given** o mesmo template, **When** Beatriz baixa o Excel, **Then**
   recebe um `.xlsx` com uma planilha cuja primeira linha traz o mesmo
   cabeçalho do CSV e nenhuma outra linha preenchida.
6. **Given** um template sem colunas, **When** Beatriz baixa qualquer
   formato, **Then** o cabeçalho traz só as três colunas fixas.
7. **Given** uma coluna adicionada na posição 2 de um template com colunas
   nas posições 1 e 5, **When** Beatriz baixa o arquivo, **Then** a ordem
   segue as posições (1, 2, 5), sem exigir posições contíguas.
8. **Given** vários templates no catálogo, **When** Beatriz lista o catálogo,
   **Then** recebe os templates paginados, com o estado de travamento de
   cada um, no padrão de listagem da API.

---

### User Story 2 - Recusar coluna inválida (Priority: P1)

Beatriz erra ao adicionar ou alterar uma coluna. O sistema recusa a operação,
diz qual regra ela violou e não grava nada.

**Why this priority**: critério de aceite da issue. Uma chave duplicada ou
inválida quebraria a leitura dos resultados na #30.

**Independent Test**: tentar cada violação contra um template existente e
conferir a recusa, o código de erro e que as colunas ficaram iguais.

**Acceptance Scenarios**:

1. **Given** uma coluna com a chave `viabilidade`, **When** Beatriz adiciona
   outra coluna com a mesma chave, **Then** a operação é recusada como chave
   duplicada.
2. **Given** um template qualquer, **When** Beatriz adiciona uma coluna com a
   chave `codigo_amostra`, `experimento` ou `replica`, **Then** a operação é
   recusada como chave reservada.
3. **Given** um template qualquer, **When** Beatriz usa uma chave fora do
   formato (com maiúscula, iniciada por dígito ou `_`, com espaço, hífen ou
   acento, vazia ou com mais de 64 caracteres), **Then** a operação é
   recusada como chave inválida.
4. **Given** um template qualquer, **When** Beatriz informa um tipo fora de
   `text`, `integer`, `decimal`, `date` e `select`, **Then** a operação é
   recusada como tipo inválido.
5. **Given** um template qualquer, **When** Beatriz cria uma coluna `select`
   sem opções, ou com lista vazia, **Then** a operação é recusada.
6. **Given** um template qualquer, **When** Beatriz cria uma coluna de outro
   tipo com opções, **Then** a operação é recusada.
7. **Given** uma coluna na posição 3, **When** Beatriz adiciona outra coluna
   na posição 3, **Then** a operação é recusada como posição ocupada.
8. **Given** um template qualquer, **When** Beatriz informa posição 0 ou
   negativa, **Then** a operação é recusada.
9. **Given** uma coluna `select`, **When** Beatriz a altera para `text` sem
   remover as opções, **Then** a operação é recusada; ao remover as opções
   na mesma alteração, ela é aceita.
10. **Given** um template qualquer, **When** Beatriz cria um template ou o
    altera com mínimo de experimentos ou de réplicas menor que 1, **Then** a
    operação é recusada.

---

### User Story 3 - Travar a estrutura depois que a Etapa 3 começa (Priority: P1)

Paulo cria um processo escolhendo o template de Beatriz. O processo avança e
a definição das amostras conclui. A partir daí, Beatriz não consegue mais
mudar as colunas nem os mínimos desse template, porque os laboratórios vão
preencher o arquivo-modelo com essa estrutura. Ela ainda corrige o nome e a
descrição, baixa o arquivo e outros processos continuam escolhendo o
template.

**Why this priority**: critério de aceite da issue. Mudar a estrutura com o
estudo em execução invalidaria os resultados enviados na #30.

**Independent Test**: vincular o template a um processo, concluir a
definição das amostras e tentar cada alteração estrutural; conferir a recusa
e que as alterações não estruturais e a seleção por processo novo seguem
aceitas.

**Acceptance Scenarios**:

1. **Given** um template vinculado a processos que ainda não concluíram a
   definição das amostras, **When** Beatriz altera, adiciona ou exclui uma
   coluna, **Then** a operação é aceita.
2. **Given** um template vinculado a um processo com a definição das amostras
   concluída, **When** Beatriz adiciona, altera ou exclui uma coluna, **Then**
   a operação é recusada como template travado e nada muda.
3. **Given** o mesmo template travado, **When** Beatriz altera o mínimo de
   experimentos ou de réplicas, **Then** a operação é recusada como template
   travado.
4. **Given** o mesmo template travado, **When** Beatriz altera só o nome ou a
   descrição, **Then** a operação é aceita.
5. **Given** o mesmo template travado, **When** Beatriz consulta, lista ou
   baixa o arquivo-modelo, **Then** recebe o estado travado e o arquivo
   normalmente.
6. **Given** o mesmo template travado, **When** alguém cria um processo
   escolhendo esse template, **Then** a criação é aceita.
7. **Given** um processo cancelado ou arquivado que concluiu a definição das
   amostras antes, **When** Beatriz tenta uma alteração estrutural no
   template dele, **Then** a operação continua recusada.
8. **Given** a definição das amostras de um processo vinculado concluindo ao
   mesmo tempo que Beatriz altera uma coluna, **When** as duas operações
   terminam, **Then** ou a alteração entrou antes da conclusão, ou foi
   recusada; nunca fica gravada uma alteração estrutural depois da
   conclusão.

---

### User Story 4 - Escolher o template de coleta ao criar o processo (Priority: P2)

Paulo cria um processo e informa o template de coleta. O processo guarda o
vínculo, e a consulta do processo o mostra. Quem cria um processo sem o campo
segue como hoje, com o vínculo vazio.

**Why this priority**: o travamento depende do vínculo, e a #30 vai exigir um
processo vinculado. Sem o campo opcional, nenhum template trava.

**Independent Test**: criar um processo com o campo e outro sem; conferir o
vínculo na consulta de cada um e a recusa com um template inexistente.

**Acceptance Scenarios**:

1. **Given** um template existente, **When** quem pode informar o campo cria
   um processo com ele, **Then** o processo é criado com o vínculo, e a
   consulta e a listagem de processos mostram o identificador do template.
2. **Given** qualquer usuário autenticado, **When** ele cria um processo sem
   o campo, **Then** a criação segue igual à de hoje e o vínculo fica vazio.
3. **Given** um identificador que não corresponde a template existente,
   **When** alguém cria um processo com ele, **Then** a criação é recusada e
   nenhum processo é criado.
4. **Given** um usuário sem a permissão de gestão do catálogo, **When** ele
   cria um processo com o campo, mesmo com um template existente, **Then** a
   criação é recusada por falta de permissão e nenhum processo é criado.
5. **Given** um processo criado, **When** alguém tenta trocar o template de
   coleta, **Then** não existe operação para isso.
6. **Given** a criação de um processo com o campo, **When** a trilha do
   processo é consultada, **Then** o evento de criação traz o identificador
   do template vinculado.

---

### User Story 5 - Excluir uma coluna antes do travamento (Priority: P3)

Beatriz percebe que `lote_reagente` sobrou e exclui a coluna. Ela some da
consulta e do arquivo-modelo, e a chave e a posição ficam livres para outra
coluna.

**Why this priority**: sem exclusão, um erro de cadastro só se corrige
criando outro template. O caso é menos frequente que a criação.

**Independent Test**: excluir uma coluna, conferir consulta e arquivo, depois
criar outra coluna com a mesma chave e posição.

**Acceptance Scenarios**:

1. **Given** um template destravado com a coluna `lote_reagente`, **When**
   Beatriz a exclui, **Then** a coluna deixa de aparecer na consulta e no
   arquivo-modelo, e o registro guarda quem excluiu e quando.
2. **Given** a coluna excluída, **When** Beatriz cria outra coluna com a
   mesma chave e a mesma posição, **Then** a operação é aceita.
3. **Given** uma coluna já excluída ou inexistente, **When** Beatriz tenta
   alterá-la ou excluí-la, **Then** a operação é recusada como não
   encontrada.

---

### User Story 6 - Restringir a gestão do catálogo (Priority: P1)

Só quem tem a permissão de gestão do catálogo cria, altera, consulta e lista
templates de coleta e baixa o arquivo-modelo. Admin e BraCVAM recebem a
permissão de fábrica.

**Why this priority**: o catálogo é global e afeta todos os processos que o
usam.

**Independent Test**: repetir cada operação com um usuário sem a permissão e
sem autenticação; conferir a recusa e que nada mudou.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado sem a permissão, **When** ele cria ou
   altera um template, ou cria, altera ou exclui uma coluna, **Then** a
   operação é recusada por falta de permissão e nada é gravado.
2. **Given** um usuário autenticado sem a permissão, **When** ele consulta
   ou lista templates ou baixa o arquivo-modelo, **Then** a operação é
   recusada por falta de permissão.
3. **Given** uma requisição sem autenticação, **When** ela chama qualquer
   operação do catálogo, **Then** ela é recusada como não autenticada.
4. **Given** a instalação inicial ou a atualização do banco, **When** o
   sistema prepara os perfis, **Then** Admin e BraCVAM têm a permissão nova
   e os demais perfis não.

---

### Edge Cases

- Template inexistente em consulta, alteração, criação de coluna ou download:
  recusa como não encontrado.
- Coluna de outro template, informada com o identificador do template
  errado: recusa como não encontrada.
- Duas criações simultâneas de coluna com a mesma chave ou a mesma posição:
  uma entra e a outra é recusada como duplicada ou ocupada, sem erro
  genérico.
- Duas criações simultâneas de coluna sem posição: as duas entram com
  posições distintas, ou uma é recusada como posição ocupada; nunca duas
  colunas ativas na mesma posição.
- Opções de `select` com item vazio ou repetido: recusa.
- Rótulo vazio ou nome do template vazio: recusa.
- Rótulo com `;`, aspas ou acentos: o rótulo não vai para o arquivo, então o
  cabeçalho não muda.
- Formato de download diferente de CSV e Excel: recusa.
- Campos desconhecidos no corpo de qualquer operação: recusa, como no resto
  da API.

## Requirements *(mandatory)*

### Functional Requirements

**Catálogo e template**

- **FR-001**: O sistema DEVE permitir criar um template de coleta com nome
  (obrigatório, 1 a 255 caracteres), descrição (opcional), mínimo de
  experimentos e mínimo de réplicas (obrigatórios, inteiros maiores ou
  iguais a 1).
- **FR-002**: O sistema DEVE permitir alterar nome, descrição e mínimos de um
  template, com as mesmas validações da criação.
- **FR-003**: O sistema DEVE permitir consultar um template com suas colunas
  ativas ordenadas por posição e o estado de travamento.
- **FR-004**: O sistema DEVE listar os templates do catálogo com paginação e
  ordenação no padrão de listagem da API, trazendo o estado de travamento de
  cada um.

**Colunas**

- **FR-005**: O sistema DEVE permitir adicionar uma coluna com rótulo
  (obrigatório, 1 a 255 caracteres), chave técnica, tipo, obrigatoriedade
  (padrão: não obrigatória), opções e posição (opcional).
- **FR-006**: A chave técnica DEVE casar com `^[a-z][a-z0-9_]{0,63}$`, ser
  única entre as colunas ativas do template e ser diferente de
  `codigo_amostra`, `experimento` e `replica`.
- **FR-007**: O tipo DEVE ser `text`, `integer`, `decimal`, `date` ou
  `select`. `select` DEVE ter ao menos uma opção; os demais tipos NÃO DEVEM
  ter opções. Cada opção DEVE ser texto não vazio e não repetido na mesma
  coluna.
- **FR-008**: A posição DEVE ser inteiro maior ou igual a 1 e única entre as
  colunas ativas do template. Sem posição informada, a coluna DEVE receber a
  maior posição ativa mais 1 (ou 1, se não houver colunas).
- **FR-009**: O sistema DEVE permitir alterar rótulo, chave técnica, tipo,
  obrigatoriedade, opções e posição de uma coluna, validando o estado
  resultante com as regras de FR-006 a FR-008.
- **FR-010**: O sistema DEVE permitir excluir uma coluna. A coluna excluída
  NÃO DEVE aparecer na consulta nem no arquivo-modelo, e sua chave e posição
  DEVEM ficar livres. O registro DEVE guardar quem excluiu e quando.
- **FR-011**: Toda recusa DEVE ter código de erro estável e distinto, no
  formato de erro da API, para: chave duplicada, chave reservada, opções
  inválidas para o tipo, posição ocupada, template travado e template ou
  coluna não encontrados. Chave fora do formato, tipo fora da lista e
  posição ou mínimo menor que 1 são erros de validação de entrada: DEVEM
  usar o código de validação da API, com o campo e o código próprio de
  cada regra na lista de campos.

**Arquivo-modelo**

- **FR-012**: O sistema DEVE gerar o arquivo-modelo de um template em CSV e em
  Excel (`.xlsx`), só com o cabeçalho.
- **FR-013**: O cabeçalho DEVE começar por `codigo_amostra`, `experimento` e
  `replica`, nessa ordem, seguidos das colunas ativas em ordem crescente de
  posição, identificadas pela chave técnica.
- **FR-014**: O CSV DEVE usar UTF-8 com BOM e separador `;`.
- **FR-015**: O Excel DEVE ter uma única planilha com o cabeçalho na primeira
  linha, sem validação de lista e sem outras linhas preenchidas.
- **FR-016**: O download DEVE indicar o tipo de conteúdo do formato e sugerir
  um nome de arquivo.

**Travamento**

- **FR-017**: Um template DEVE ser considerado travado quando ao menos um
  processo vinculado a ele, em qualquer situação (aberto, encerrado,
  cancelado, arquivado ou excluído), tem a definição das amostras
  concluída. O sistema DEVE calcular o estado na hora de cada operação.
- **FR-018**: Com o template travado, o sistema DEVE recusar a adição,
  alteração e exclusão de colunas e a alteração dos mínimos, e DEVE aceitar a
  alteração de nome e descrição, a consulta, a listagem, o download e a
  seleção por processo novo.
- **FR-019**: O sistema NÃO DEVE gravar uma alteração estrutural depois que a
  conclusão da definição das amostras de um processo vinculado for gravada,
  inclusive com as duas operações simultâneas.

**Vínculo com o processo**

- **FR-020**: A criação de processo DEVE aceitar o identificador opcional de
  um template de coleta e gravá-lo no processo. Sem o campo, o vínculo fica
  vazio e a criação segue como hoje.
- **FR-021**: A criação DEVE ser recusada, sem criar o processo, quando o
  identificador não corresponde a um template existente.
- **FR-022**: Só quem tem a permissão de FR-026 DEVE poder informar o campo.
  Para os demais, a criação com o campo DEVE ser recusada por falta de
  permissão, sem criar o processo.
- **FR-023**: A consulta e a listagem de processos DEVEM trazer o
  identificador do template de coleta vinculado, ou vazio.
- **FR-024**: O evento de criação do processo na trilha DEVE trazer o
  identificador do template vinculado, quando houver.
- **FR-025**: NÃO DEVE existir operação para trocar ou remover o template de
  coleta de um processo.

**Autorização**

- **FR-026**: O sistema DEVE ter uma permissão nova de gestão do catálogo de
  templates de coleta, concedida ao Admin e à BraCVAM na instalação inicial e
  na atualização do banco.
- **FR-027**: Criar e alterar template e criar, alterar e excluir coluna
  DEVEM exigir a permissão de FR-026.
- **FR-028**: Consultar, listar e baixar o arquivo-modelo DEVEM exigir a
  permissão de FR-026.
- **FR-029**: As operações que alteram dados DEVEM seguir a mesma proteção de
  origem das demais operações de escrita da API.

**Fora de escopo**

- **FR-030**: Esta entrega NÃO DEVE incluir colunas derivadas, a flag de
  ensaios fracassados, reordenação em lote, exclusão do template, envio ou
  leitura de resultados (#30) e o acesso do laboratório ao arquivo-modelo do
  seu processo.

### Key Entities

- **Template de coleta**: entrada do catálogo global. Nome, descrição,
  mínimo de experimentos, mínimo de réplicas, autoria e datas de criação,
  alteração e exclusão. O estado de travamento sai dos processos vinculados
  e não fica guardado.
- **Coluna do template de coleta**: pertence a um template. Rótulo, chave
  técnica, tipo, obrigatoriedade, opções, posição, autoria e datas de
  criação, alteração e exclusão.
- **Colunas fixas**: `codigo_amostra`, `experimento` e `replica`. Abrem todo
  arquivo-modelo e não ficam no cadastro.
- **Processo** (existente, ampliado): ganha o vínculo opcional com um
  template de coleta, definido só na criação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Com o template de seis colunas de tipos mistos, o CSV e o Excel
  baixados trazem exatamente nove cabeçalhos na ordem esperada, nos dois
  formatos.
- **SC-002**: Cada violação listada na User Story 2 gera recusa com o código
  de erro próprio e deixa as colunas do template idênticas às de antes.
- **SC-003**: Depois que a definição das amostras de um processo vinculado
  conclui, nenhuma tentativa de alteração estrutural é aceita, e 100% das
  alterações de nome e descrição, downloads e seleções por processo novo são
  aceitas.
- **SC-004**: Todos os testes atuais de criação de processo passam sem
  alteração, sem o campo novo.
- **SC-005**: Nenhuma operação de escrita do catálogo é aceita para usuário
  sem a permissão nova.
- **SC-006**: O CSV abre numa planilha comum com cada cabeçalho na própria
  coluna, sem configuração manual.

## Assumptions

- A exclusão de coluna preserva o registro com quem excluiu e quando, como os
  demais catálogos. A exclusão do template inteiro fica fora: um template
  pode estar vinculado a processos, e nenhuma fonte define o que acontece
  com eles.
- O nome do template não precisa ser único. Os processos escolhem pelo
  identificador.
- Mudanças no catálogo não entram na trilha de eventos, que exige um
  processo. A autoria e as datas de cada registro cobrem a rastreabilidade
  pedida na decisão 1.
- A definição das amostras não reabre (Spec 031), então um template travado
  não volta a destravar. Um processo excluído continua contando: a exclusão
  é lógica e vale para processos em andamento, inclusive depois da
  definição das amostras.
- Um template sem colunas é válido. Ele gera o arquivo-modelo só com as três
  colunas fixas.
- Alterar o template não muda processos nem arquivos já baixados. Antes do
  travamento, quem baixou o arquivo pode ter uma estrutura antiga; a #30
  valida o arquivo enviado contra a estrutura atual.
- O mínimo de experimentos e de réplicas fica guardado e aparece na consulta.
  A #30 é quem o aplica aos resultados enviados.
- Um processo criado por proponente sem a permissão fica sem template de
  coleta, e nenhuma operação o vincula depois. A #30 vai exigir o vínculo;
  como o processo recebe o template nesse caso fica registrado como
  pendência para a #30 em `docs/observacoes-e-pendencias.md`.
- A obrigatoriedade e o tipo das colunas não aparecem no arquivo-modelo. A
  #30 é quem os aplica aos resultados enviados.
- Depende de: Spec 031 (definição das amostras), Spec 034 (formato de erro),
  Specs 032/033 (padrão de listagem) e Spec 040 (Etapa 3 nos templates de
  processo).

# Feature Specification: Anexos de Arquivo em Formulários

**Feature Branch**: `016-form-attachments`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Crie uma gitworktree a partir da branch atual, implemente para mim os endpoints necessarios para que seja possivel adicionar anexos nos formulários (isso vale para docx, pdf, img e etc) elabore de uma forma que eu consiga por exemplo como proponente, adicionar um pop no momento da submissçao, anexo de arquivos não podem ser avaliados por IA ainda, não repasse isso para api, apenas vamos mockar internamente"

## Overview

Hoje os formulários de processo aceitam apenas dados estruturados (texto, número,
data, escolha). O motor de formulários já reconhece o tipo de campo `file_upload`
na sintaxe YAML e o modelo de dados já reserva o vínculo entre um valor de campo e
um artefato de arquivo, mas **não existe forma de o proponente enviar o arquivo**:
salvar rascunho e submeter recusam explicitamente campos `file_upload`.

Esta feature entrega a capacidade de **anexar arquivos a campos de formulário**.
O caso de uso condutor é o proponente que, ao preencher a submissão de uma
proposta, precisa anexar um documento de apoio — por exemplo, um Procedimento
Operacional Padrão (POP) — em PDF, DOCX, imagem ou formato equivalente, e
submeter a proposta com esse anexo incluído no dossiê.

Dois limites explícitos desta entrega:

1. **Anexos não são avaliados por IA.** Campos de arquivo ficam fora do pipeline
   de pré-avaliação automática. O conteúdo do arquivo **não** é enviado ao
   provedor de IA; o sistema registra internamente, de forma determinística, que
   o campo não foi avaliado.
2. **Sem integração externa de armazenamento nesta entrega.** O arquivo é
   persistido pelo próprio backend; qualquer serviço externo de storage,
   antivírus ou pré-visualização fica fora de escopo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Proponente anexa um documento e submete a proposta (Priority: P1)

Como proponente preenchendo o formulário de submissão de um processo, eu envio um
arquivo (por exemplo, o POP do método em PDF ou DOCX) para o campo de anexo do
formulário e, em seguida, submeto a proposta. O anexo passa a fazer parte do
dossiê da submissão.

**Why this priority**: É o objetivo central da feature. Sem o envio do arquivo e
sua inclusão na submissão, nada mais tem valor.

**Independent Test**: Instanciar um processo cujo formulário de submissão tenha um
campo de anexo, autenticar como proponente, enviar um arquivo válido para esse
campo, preencher os demais campos obrigatórios e submeter; confirmar que a
submissão conclui e que o anexo fica associado ao dossiê gerado.

**Acceptance Scenarios**:

1. **Given** um formulário de submissão com um campo de anexo e o proponente
   autenticado, **When** ele envia um arquivo PDF dentro do limite de tamanho e
   de extensão permitida, **Then** o arquivo é aceito, associado ao campo e passa
   a aparecer no formulário como anexo presente (nome do arquivo, tamanho e tipo).
2. **Given** um campo de anexo que já tem um arquivo enviado, **When** o
   proponente envia um novo arquivo para o mesmo campo, **Then** o novo arquivo
   substitui o anterior e apenas um anexo permanece associado ao campo.
3. **Given** um campo de anexo obrigatório sem arquivo enviado, **When** o
   proponente tenta submeter o formulário, **Then** a submissão é recusada com uma
   mensagem clara indicando que o anexo é obrigatório.
4. **Given** todos os campos obrigatórios preenchidos e o anexo enviado, **When**
   o proponente submete a proposta, **Then** a submissão conclui, o formulário
   fica marcado como submetido e o anexo consta no dossiê da submissão.
5. **Given** um formulário já submetido, **When** o proponente tenta enviar,
   substituir ou remover um anexo desse formulário, **Then** a operação é recusada
   porque o formulário submetido é imutável.

---

### User Story 2 - Proponente gerencia anexos durante o rascunho (Priority: P2)

Antes de submeter, o proponente pode enviar, substituir e remover anexos quantas
vezes precisar, salvando o rascunho do formulário normalmente entre as
alterações. Os anexos já enviados permanecem associados ao rascunho quando ele
reabre o formulário mais tarde.

**Why this priority**: Torna o fluxo utilizável na prática (o proponente raramente
acerta o documento de primeira), mas o valor mínimo já é entregue pela User
Story 1.

**Independent Test**: Como proponente, enviar um anexo, salvar o rascunho, sair,
reabrir o formulário e confirmar que o anexo ainda está lá; depois substituí-lo,
salvar de novo e reabrir; por fim remover o anexo e confirmar que o campo volta a
ficar vazio.

**Acceptance Scenarios**:

1. **Given** um rascunho de formulário com um campo de anexo, **When** o
   proponente envia um arquivo e depois salva o rascunho com os demais campos,
   **Then** o salvamento do rascunho conclui sem erro e o anexo permanece
   associado ao campo.
2. **Given** um rascunho com um anexo já enviado, **When** o proponente reabre o
   formulário, **Then** o campo de anexo indica o arquivo presente (nome, tamanho,
   tipo) sem exigir novo envio.
3. **Given** um rascunho com um anexo já enviado, **When** o proponente remove o
   anexo, **Then** o campo volta a ficar vazio e, se o campo for obrigatório, a
   submissão passa a ser bloqueada até um novo envio.
4. **Given** um envio de arquivo com extensão não permitida ou acima do limite de
   tamanho do campo, **When** o proponente tenta enviá-lo, **Then** o envio é
   recusado com mensagem clara e o estado anterior do campo é preservado.

---

### User Story 3 - Avaliador de triagem consulta os anexos da proposta (Priority: P2)

Quem avalia a proposta na triagem precisa abrir e baixar os arquivos anexados
pelo proponente para analisá-los junto com o restante do dossiê.

**Why this priority**: Um anexo que ninguém consegue abrir não cumpre seu
propósito; porém depende de já existir o envio (User Story 1).

**Independent Test**: Com uma proposta submetida contendo um anexo, autenticar
como avaliador de triagem autorizado e baixar o arquivo; confirmar que o conteúdo
recebido é idêntico ao enviado. Repetir como usuário sem permissão e confirmar a
recusa.

**Acceptance Scenarios**:

1. **Given** uma proposta submetida com um anexo e um avaliador de triagem
   autorizado, **When** ele solicita o download do anexo, **Then** recebe o
   arquivo original com o nome e o tipo corretos.
2. **Given** o mesmo anexo, **When** um usuário sem permissão de leitura sobre
   aquele processo solicita o download, **Then** o acesso é negado sem revelar a
   existência ou o conteúdo do arquivo.
3. **Given** a listagem do formulário de uma proposta, **When** um leitor
   autorizado a consulta, **Then** cada campo de anexo mostra os metadados do
   arquivo (nome, tamanho, tipo, data de envio) e um meio de obter o arquivo.

---

### User Story 4 - Anexos ficam fora da avaliação por IA (Priority: P3)

Quando a pré-avaliação automática por IA é disparada para uma submissão que
contém campos de anexo, esses campos são ignorados pelo pipeline: o conteúdo do
arquivo não é enviado ao provedor de IA e o resultado registra o campo como "não
avaliado".

**Why this priority**: É uma salvaguarda de conformidade e custo, não uma
funcionalidade percebida diretamente pelo usuário; o comportamento é "não fazer
algo".

**Independent Test**: Submeter uma proposta cujo formulário tenha um campo de
anexo associado a uma configuração de avaliação por IA; disparar a pré-avaliação
e confirmar, no registro da execução, que o campo de anexo aparece como não
avaliado e que nenhuma chamada ao provedor de IA foi feita para ele.

**Acceptance Scenarios**:

1. **Given** uma configuração de avaliação por IA que alcança um campo de anexo,
   **When** a pré-avaliação roda, **Then** nenhum conteúdo de arquivo é enviado ao
   provedor de IA.
2. **Given** a mesma execução, **When** ela conclui, **Then** o campo de anexo é
   registrado com um resultado determinístico de "não avaliado por IA" e a
   execução como um todo não falha por causa dele.
3. **Given** um formulário que só tem campos de anexo alcançados por IA, **When**
   a pré-avaliação roda, **Then** ela conclui com sucesso e sem itens avaliados
   por IA, em vez de ficar pendente ou falhar.

---

### Edge Cases

- **Arquivo vazio (0 byte) ou requisição sem arquivo**: envio recusado com
  mensagem clara; estado anterior do campo preservado.
- **Envio para um campo que não é do tipo anexo**: recusado como campo
  incompatível.
- **Envio para um campo inexistente no formulário**: recusado como campo
  desconhecido.
- **Extensão do arquivo diverge do tipo real do conteúdo**: nesta entrega a
  validação é por extensão declarada e limite de tamanho; a inspeção de conteúdo
  fica fora de escopo e deve ser registrada como lacuna conhecida.
- **Substituição concorrente do mesmo campo por dois envios**: o resultado
  converge para um único anexo associado ao campo, sem registros órfãos ativos.
- **Remoção de anexo já submetido**: bloqueada (formulário submetido é imutável);
  a remoção lógica só é possível enquanto o formulário está em rascunho.
- **Download de anexo cujo processo foi excluído logicamente**: tratado conforme
  o mesmo escopo de leitura do processo — se o leitor não enxerga mais o
  processo, não enxerga o anexo.
- **Limite de tamanho não declarado no campo**: aplica-se um teto padrão do
  sistema.

## Requirements *(mandatory)*

### Functional Requirements

#### Envio e associação

- **FR-001**: O sistema MUST permitir que o proponente responsável por uma
  execução de atividade de formulário envie um arquivo para um campo do tipo
  anexo desse formulário.
- **FR-002**: O sistema MUST associar cada arquivo enviado ao campo específico do
  formulário e à execução da atividade correspondente, registrando ao menos:
  nome original do arquivo, tamanho, tipo de conteúdo, soma de verificação de
  integridade e data/autor do envio.
- **FR-003**: Cada campo de anexo MUST conter no máximo um arquivo por vez; um
  novo envio para o mesmo campo substitui o anterior, e o arquivo substituído
  deixa de estar ativo.
- **FR-004**: O sistema MUST permitir que o proponente remova o anexo de um campo
  enquanto o formulário estiver em rascunho, deixando o campo vazio.
- **FR-005**: O sistema MUST recusar envio, substituição ou remoção de anexo em um
  formulário já submetido, com mensagem indicando que a submissão é imutável.

#### Tipos e limites

- **FR-006**: O sistema MUST aceitar, no mínimo, os formatos PDF, DOCX e imagens
  comuns (PNG, JPEG), além de qualquer conjunto de extensões declarado no próprio
  campo (`allowed_extensions`).
- **FR-007**: Quando o campo declara `allowed_extensions`, o sistema MUST recusar
  arquivos de extensão fora dessa lista.
- **FR-008**: O sistema MUST recusar arquivos acima do limite de tamanho do campo
  (`max_size_mb`) ou, na ausência dele, acima do teto padrão do sistema.
- **FR-009**: O sistema MUST recusar requisições de envio sem arquivo ou com
  arquivo de tamanho zero.
- **FR-010**: Toda recusa de envio MUST preservar o anexo anterior do campo, se
  houver, e MUST NOT vazar detalhes internos de infraestrutura na mensagem de
  erro.

#### Rascunho e submissão

- **FR-011**: O salvamento de rascunho do formulário MUST concluir com sucesso
  quando o formulário contém campos de anexo, preservando os anexos já enviados e
  sem exigir reenvio dos arquivos junto com os demais valores.
- **FR-012**: Na submissão do formulário, o sistema MUST validar que todo campo de
  anexo obrigatório possui um arquivo associado; caso contrário, recusa a
  submissão com erro por campo.
- **FR-013**: Ao submeter, o sistema MUST incluir os anexos no dossiê da
  submissão, de modo que fiquem recuperáveis junto com os demais valores do
  formulário.
- **FR-014**: A listagem do formulário (rascunho ou submetido) MUST expor, para
  cada campo de anexo, os metadados do arquivo presente e um meio de obtê-lo, em
  vez de um valor de texto cru.

#### Acesso e download

- **FR-015**: O sistema MUST permitir o download do arquivo original (conteúdo
  idêntico ao enviado) por quem tem permissão de leitura sobre o processo ao qual
  o anexo pertence — no mínimo: o proponente dono da submissão, os perfis
  autorizados a avaliar a triagem daquele processo e os administradores.
- **FR-016**: O sistema MUST negar o download a quem não tem permissão de leitura
  sobre o processo, sem revelar a existência nem o conteúdo do arquivo.
- **FR-017**: Toda rota de envio, substituição, remoção e download de anexo MUST
  validar o usuário autenticado e a origem confiável da requisição, conforme as
  regras de segurança do projeto.

#### Avaliação por IA (mock interno)

- **FR-018**: O sistema MUST excluir campos do tipo anexo do pipeline de
  pré-avaliação automática por IA: o conteúdo do arquivo MUST NOT ser enviado ao
  provedor de IA.
- **FR-019**: Quando uma configuração de avaliação por IA alcança um campo de
  anexo, o sistema MUST registrar para esse campo um resultado determinístico e
  interno de "não avaliado por IA" (com motivo), sem chamar o provedor.
- **FR-020**: Uma execução de pré-avaliação que contenha apenas campos de anexo
  alcançados por IA MUST concluir com sucesso (sem itens avaliados), em vez de
  ficar pendente ou falhar.

#### Auditoria e integridade

- **FR-021**: Registros de anexo MUST seguir o padrão de auditoria do projeto
  (autoria e datas de criação/atualização) e a remoção MUST ser lógica,
  preservando histórico.
- **FR-022**: O sistema MUST armazenar a soma de verificação do conteúdo para
  permitir comprovar a integridade do arquivo entregue no download.

### Key Entities *(include if feature involves data)*

- **Anexo de Formulário**: o arquivo enviado pelo proponente e seus metadados
  (nome original, tamanho, tipo de conteúdo, soma de verificação, status, autoria
  e datas). Pertence a uma execução de atividade dentro de um processo.
- **Campo de Anexo**: campo de formulário do tipo `file_upload`, com configuração
  opcional de extensões permitidas, limite de tamanho, obrigatoriedade e seção.
- **Valor de Campo de Anexo**: o vínculo entre um campo de anexo de uma instância
  de formulário e o Anexo de Formulário ativo naquele campo (no máximo um).
- **Instância de Formulário**: a resposta do proponente a um formulário de uma
  atividade; pode estar em rascunho (anexos editáveis) ou submetida (imutável).
- **Dossiê da Submissão**: o artefato consolidado gerado na submissão, que passa a
  referenciar os anexos além dos demais valores.
- **Execução de Pré-Avaliação por IA**: processo automático que, a partir desta
  feature, ignora campos de anexo e registra-os como não avaliados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um proponente consegue, do formulário em branco até a proposta
  submetida com um anexo válido, concluir o fluxo em menos de 3 minutos e sem
  nenhum passo manual fora da interface do formulário.
- **SC-002**: 100% dos downloads de um anexo por um leitor autorizado retornam um
  arquivo cuja soma de verificação é idêntica à do arquivo enviado.
- **SC-003**: 100% das tentativas de download por usuário sem permissão de leitura
  sobre o processo são negadas.
- **SC-004**: Arquivos com extensão não permitida pelo campo ou acima do limite de
  tamanho são recusados em 100% dos casos, sem alterar o anexo anterior.
- **SC-005**: Nenhuma execução de pré-avaliação por IA envia conteúdo de arquivo
  ao provedor de IA; campos de anexo aparecem como "não avaliado" em 100% das
  execuções que os alcançam.
- **SC-006**: Uma submissão com campo de anexo obrigatório vazio é bloqueada em
  100% das tentativas, com erro identificando o campo.
- **SC-007**: Salvar rascunho de um formulário com campos de anexo conclui com
  sucesso em 100% dos casos, preservando os anexos já enviados (nenhuma regressão
  em relação ao comportamento atual de rascunho para os demais tipos de campo).
- **SC-008**: `poe format`, `poe lint` e `poe test` permanecem verdes após a
  entrega, e a migração de banco correspondente tem teste de upgrade e downgrade.
- **SC-009**: Existe uma demonstração em `demos/` que exercita, contra a API real,
  o envio de um anexo pelo proponente, a submissão e o download pelo avaliador,
  com um seed que provisiona a massa mínima necessária.

## Assumptions

- **Fluxo do Spec Kit**: esta invocação (`/speckit-specify`) produz apenas a
  especificação. A criação da git worktree e a implementação dos endpoints
  ocorrem nas fases seguintes (`/speckit-plan`, `/speckit-tasks`,
  `/speckit-implement`), conforme a constituição do projeto (nada de código antes
  de `spec.md` e `plan.md` aprovados).
- **Reuso do modelo existente**: o tipo de campo `file_upload` já documentado na
  sintaxe YAML e o vínculo já reservado entre valor de campo e artefato de
  arquivo são a base; esta feature os torna operacionais em vez de introduzir um
  conceito novo de formulário.
- **Um arquivo por campo**: o caso de uso ("adicionar um POP") é de um único
  documento por campo. Múltiplos arquivos por campo ficam fora de escopo; formam
  vários campos de anexo quem precisar de vários documentos.
- **Armazenamento pelo backend**: o arquivo é persistido pela própria aplicação
  (sem serviço externo de storage nesta entrega). A localização física é decisão
  de `plan.md`.
- **Validação por extensão e tamanho**: a validação de tipo é pela extensão
  declarada e pelo limite de tamanho; não há inspeção do conteúdo real do arquivo
  nem verificação antivírus nesta entrega.
- **Teto padrão de tamanho**: quando o campo não declara `max_size_mb`, aplica-se
  um limite padrão do sistema, definido em `plan.md` (assumido em 25 MB, alinhado
  aos exemplos da sintaxe YAML).
- **Escopo de acesso**: o download segue o mesmo escopo de leitura já aplicado ao
  processo/formulário (proponente dono, avaliadores de triagem autorizados,
  administradores); esta feature não cria um novo modelo de permissão.
- **Anexos durante o rascunho**: o proponente pode enviar/substituir/remover
  anexos enquanto o formulário está em rascunho; após a submissão tudo fica
  imutável. Isso amplia o comportamento atual, que recusa `file_upload` no
  rascunho.
- **"Mockar internamente" a IA**: significa que o pipeline de IA não processa
  anexos e registra um resultado interno determinístico de "não avaliado"; não
  há nova dependência nem novo endpoint de IA.
- **Provedor de IA determinístico** continua em uso nos seeds/demos para não
  depender de chave externa.
- **Formatos**: "docx, pdf, img e etc" é interpretado como PDF, DOCX e imagens
  comuns (PNG, JPEG) como piso, além do que cada campo declarar.

## Dependencies

- Motor de processos e formulários (`pivma.core.process_engine`) e a sintaxe de
  formulários YAML (`src/pivma/templates_data/README.md`).
- Modelo de artefato de arquivo e vínculo de valor de campo já presentes no
  modelo relacional.
- Serviço de pré-avaliação por IA (Specs 010/013) para a exclusão dos campos de
  anexo do pipeline.
- Regras de autorização de leitura de processo e de triagem (Specs 003/004/014).
- Padrão de auditoria e exclusão lógica do projeto (`AuditMixin`).
- API real em execução e uma demo + seed, conforme critério de conclusão do
  `AGENTS.md` e da constituição.

## Out of Scope

- Avaliação por IA do conteúdo de anexos (texto extraído, OCR, análise de
  documento).
- Verificação antivírus, sandbox de arquivos ou inspeção do conteúdo real além
  da extensão declarada.
- Pré-visualização, miniatura ou renderização de anexos na interface.
- Histórico versionado de anexos além da substituição simples (o arquivo trocado
  deixa de estar ativo, sem galeria de versões).
- Múltiplos arquivos por campo e upload em lote.
- Integração com serviço externo de armazenamento de objetos.
- Edição de anexos após a submissão do formulário.
- Anexos em formulários de outras fases além de submissão/triagem (só entram os
  formulários que declararem campos `file_upload`).

## Pendências e Lacunas Conhecidas

- **Validação por conteúdo real**: nesta entrega confia-se na extensão declarada
  e no limite de tamanho; um arquivo renomeado (ex.: executável com extensão
  `.pdf`) não é detectado. Registrar como risco a tratar em feature futura.
- **Antivírus**: sem varredura de malware nos arquivos recebidos.
- **Limites de palavras/tamanho por campo do FP**: não afetados por esta feature,
  mas anexos podem passar a ser a via para conteúdos longos hoje mal
  representados (ver Spec 015).

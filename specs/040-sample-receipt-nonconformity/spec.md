# Feature Specification: Recebimento de amostras, inconformidades e cadastro expandido

**Feature Branch**: `feat/040-sample-receipt-nonconformity`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Vamos resolver as issues #28 e #71, e a #72, que
talvez devesse ser feita antes ou ao mesmo tempo. A API para preencher
automaticamente deve exigir confirmação do usuário e usar o PubChem." Inclui
as jornadas do analista (Thiago) e do Grupo de Seleção de Amostras (Ricardo)
enviadas pelo usuário em 2026-10-04 e as decisões registradas na issue #71.

- #72: expansão do cadastro de amostras (gabarito, faixa térmica, frasco,
  reserva técnica, pictogramas GHS) e autopreenchimento por consulta externa.
- #28: confirmação de recebimento de amostras pelo laboratório participante.
- #71: problema no recebimento: aviso a quem despachou, resolução e reenvio.
  Absorve o escopo da #29 (tratamento de inconformidade).

## Contexto

- **CONFIRMADO, fonte oficial**: o Plano de Trabalho exige que a plataforma
  "deve também gerir o processo de eventuais problemas e ou perdas das
  amostras" (seção 2), o check-in das amostras com o registro das condições
  (RF040), o controle de acesso por laboratório (RF044) e o monitoramento do
  recebimento (RF046).
- **CONFIRMADO NO MATERIAL** (`docs/guia-prototipo.md`, `05.1 - Confirmação de
  recebimento de amostras`): o laboratório registra o recebimento com as
  condições adequado, avariado, temperatura incorreta e vazamento ou quebra.
  O protótipo não mostra quem é avisado nem se a condição inadequada bloqueia
  a execução (`DÚVIDA / PONTO A VALIDAR`). Esta spec decide os dois pontos.
- **CONFIRMADO, implementação atual**: o Grupo de Seleção de Amostras
  cadastra as substâncias e gera um código cego por substância e laboratório
  (Spec 031). Só ele lê substâncias, códigos, SDS, etiquetas e a visão cega do
  frasco. O armazenamento é texto livre; não há faixa térmica, reserva nem
  pictogramas.
- **CONFIRMADO, implementação atual**: o motor executa atividades por
  laboratório, com dispensa e reabertura por laboratório (Spec 036) e
  isolamento de visão por laboratório (Spec 037). Nenhum template declara
  ainda uma atividade por laboratório: a Etapa 3 não existe nos templates.
- **CONFIRMADO, implementação atual**: a base de notificações envia e-mails
  por fila na mesma transação da operação (Spec 036, notificações). Não existe
  central de notificações dentro da plataforma; o aviso dentro da plataforma é
  a tarefa na lista de tarefas.

## Clarifications

### Session 2026-10-04

- Q: Quem despacha, reenvia e resolve o problema no recebimento? → A: O Grupo
  de Seleção de Amostras, único detentor do mapeamento entre substância e
  código cego (issue #71, decisão 1).
- Q: O problema bloqueia o laboratório todo ou só o frasco? → A: O
  recebimento do laboratório afetado só conclui com o lote completo. O ensaio
  roda todas as amostras na mesma corrida, para evitar efeito de lote. Os
  demais laboratórios seguem (issue #71, decisão 2).
- Q: O reenvio mantém o código ou gera um novo? → A: Código novo. O vínculo
  entre o código novo e o anterior fica registrado e só o Grupo de Seleção o
  vê. A Jornada 4 enviada pelo usuário, que falava em "mesmo código cego",
  foi ajustada a esta decisão (issue #71, decisão 3; confirmado pelo usuário
  em 2026-10-04).
- Q: O problema é registrado por frasco ou por remessa? → A: Por frasco
  (código cego); cada frasco tem sua condição e sua decisão (issue #71,
  decisão 4).
- Q: Quem lê a classificação de referência (gabarito)? → A: Por ora, só o
  Grupo de Seleção de Amostras, como o resto do conteúdo das amostras (Spec
  031). A leitura pelo Grupo Gestor e pelo Estatístico, pedida na #72, fica
  para a Etapa 4, quando houver análise a fazer e o momento de abrir o
  cegamento estiver definido (usuário, 2026-10-04).
- Q: Como o reenvio usa a reserva técnica? → A: Cada reenvio debita um frasco
  da reserva da substância. Com reserva zero o reenvio é recusado e o Grupo
  escolhe entre aceitar com ressalva e desclassificar (usuário, 2026-10-04).
- Q: O registro do frasco aceita fotos? → A: Sim, imagens opcionais, vistas
  pelo próprio laboratório e pelo Grupo de Seleção (usuário, 2026-10-04).
- Q: O autopreenchimento grava dados sozinho? → A: Não. A consulta só sugere
  valores; nada é gravado até o Grupo de Seleção enviar o cadastro com os
  valores que aceitou. A fonte é o PubChem (usuário, 2026-10-04).
- Q: Como fica a #29? → A: Coberta por esta spec. A sugestão é fechá-la ao
  entregar (proposta da issue #71, decisão 5).

### Session 2026-10-04 (jornadas do usuário)

- Q: A Jornada 4 mostra uma "notificação prioritária na central" do Grupo de
  Seleção. Não há central na plataforma. Como atender? → A: A tarefa
  "Resolver problemas no recebimento de amostras" e a lista de
  inconformidades fazem o papel da central; cada inconformidade traz o texto
  "Alerta de Recebimento: o laboratório X registrou desvio térmico/físico no
  frasco Y" (FR-043).
- Q: A Jornada 2 pede que o sistema avise antes de o analista finalizar. O
  backend sustenta isso? → A: Sim, com uma pré-verificação que valida os
  campos e diz se o registro geraria inconformidade, sem gravar nada
  (FR-044). Ela serve também à Jornada 3 (habilitar o salvar).
- As jornadas do usuário e os testes que as percorrem estão em
  [journeys.md](journeys.md).

## User Scenarios & Testing *(mandatory)*

Personas: **Thiago**, analista de um laboratório participante, na bancada com
a caixa térmica aberta; **Ricardo**, do Grupo de Seleção de Amostras,
guardião do cegamento.

### User Story 1 - Cadastrar a substância com gabarito, faixa térmica, frasco e GHS (Priority: P1)

Ricardo cadastra cada substância do estudo com os dados de antes (nome, CAS,
lote, manuseio seguro, SDS) e com os dados novos: a classificação de
referência (o desfecho conhecido da substância no ensaio), o regime e a faixa
de temperatura de conservação, a quantidade por frasco e a unidade, o tipo de
recipiente, a validade da alíquota, a quantidade de frascos de reserva e os
pictogramas GHS. A classificação de referência é obrigatória e nunca aparece
para os laboratórios.

**Why this priority**: o recebimento só detecta desvio térmico sozinho se a
substância tiver faixa térmica, e o reenvio depende da reserva técnica. O
gabarito é a base da análise estatística da Etapa 4.

**Independent Test**: cadastrar uma substância com todos os campos novos e
conferir a resposta; cadastrar sem classificação de referência e conferir a
recusa; abrir a visão cega do frasco e conferir pictogramas e faixa térmica
sem nome, CAS, SDS ou gabarito.

**Acceptance Scenarios**:

1. **Given** a definição das amostras em andamento, **When** Ricardo cadastra
   uma substância com todos os campos novos válidos, **Then** a substância é
   salva com eles e os códigos cegos são gerados como antes.
2. **Given** um cadastro sem classificação de referência, ou com ela em
   branco, **When** Ricardo envia, **Then** o cadastro é recusado e nada é
   gravado.
3. **Given** um regime "refrigerado" sem faixa informada, **When** Ricardo
   cadastra, **Then** a faixa gravada é de 2 °C a 8 °C; com "ambiente", de
   15 °C a 25 °C.
4. **Given** um regime "congelado", "ultracongelado" ou "personalizado" sem
   faixa completa, **When** Ricardo cadastra, **Then** o cadastro é recusado
   indicando o campo.
5. **Given** uma faixa com mínimo maior que o máximo, **When** Ricardo
   cadastra ou altera, **Then** a operação é recusada.
6. **Given** um pictograma fora de GHS01 a GHS09, ou repetido, **When**
   Ricardo cadastra, **Then** o cadastro é recusado.
7. **Given** reserva, quantidade por frasco negativas (ou quantidade zero),
   **When** Ricardo cadastra, **Then** o cadastro é recusado.
8. **Given** uma substância cadastrada antes desta entrega, sem os campos
   novos, **When** Ricardo lista as substâncias, **Then** ela aparece com os
   campos novos vazios; ao alterá-la sem enviar a classificação de
   referência, a alteração é aceita.
9. **Given** a lista de substâncias, **When** Ricardo consulta, **Then** vê a
   reserva técnica de cada substância.
10. **Given** a visão cega do frasco e os dados de etiqueta, **When** quem tem
    acesso a eles consulta, **Then** recebem pictogramas GHS, regime e faixa
    térmica, quantidade e unidade do frasco, tipo de recipiente e validade, e
    não recebem nome químico, CAS, SDS nem classificação de referência.

---

### User Story 2 - Sugerir dados da substância a partir do CAS, com confirmação (Priority: P2)

Ricardo digita o CAS e pede a consulta. O sistema busca o composto no PubChem
e devolve sugestões: nome do composto, pictogramas GHS e o identificador do
composto na fonte. Ricardo revisa, aceita, corrige ou descarta cada sugestão
e só então envia o cadastro. Nada é gravado pela consulta.

**Why this priority**: reduz digitação e erro no cadastro, mas o cadastro
funciona sem ela.

**Independent Test**: com a fonte externa simulada, consultar um CAS conhecido
e conferir as sugestões; conferir que nenhuma substância foi criada; consultar
um CAS inexistente e outro com a fonte fora do ar.

**Acceptance Scenarios**:

1. **Given** um CAS válido que a fonte conhece, **When** Ricardo consulta,
   **Then** recebe nome sugerido, pictogramas GHS sugeridos, o identificador
   na fonte e o endereço da página do composto, e a lista de substâncias do
   processo não muda.
2. **Given** um CAS com formato ou dígito verificador inválido, **When**
   Ricardo consulta, **Then** a consulta é recusada sem chamar a fonte.
3. **Given** um CAS válido que a fonte não conhece, **When** Ricardo consulta,
   **Then** recebe a resposta "composto não encontrado".
4. **Given** a fonte fora do ar ou lenta além do limite, **When** Ricardo
   consulta, **Then** recebe a resposta "consulta indisponível" e pode
   cadastrar à mão.
5. **Given** um usuário que não é do Grupo de Seleção do processo, **When**
   consulta, **Then** a consulta é negada como as demais rotas de amostras.

---

### User Story 3 - Confirmar o recebimento de um lote em ordem (Priority: P1)

Jornada 1. Depois da conclusão da definição das amostras, Thiago abre a Etapa
3 e encontra a atividade "Confirmação de Recebimento de Amostras". Vê só os
frascos do próprio laboratório, com código, instruções de manuseio,
pictogramas e faixa térmica, sem nome, CAS, SDS ou dados de outro
laboratório. Para cada frasco, informa o código (digitado ou lido do QR), a
data e hora de abertura da caixa, a temperatura medida, o estado da
embalagem e, se quiser, uma observação. Quando o último frasco do lote é
registrado em ordem, o recebimento do laboratório conclui e a resposta diz
que o lote está na cadeia de custódia e liberado para os ensaios.

**Why this priority**: é o início da cadeia de custódia na bancada (RF040) e
a primeira atividade por laboratório real do sistema.

**Independent Test**: com dois laboratórios e duas substâncias, concluir a
definição das amostras, registrar os dois frascos do Lab A em ordem e
conferir a execução do Lab A concluída e a do Lab B em andamento.

**Acceptance Scenarios**:

1. **Given** a definição das amostras concluída, **When** Thiago lista os
   frascos do recebimento, **Then** vê só os códigos do próprio laboratório,
   cada um com o estado "pendente".
2. **Given** um frasco pendente do laboratório de Thiago e uma temperatura
   dentro da faixa, **When** ele registra o frasco com embalagem íntegra,
   **Then** o registro é salvo, o frasco passa a "recebido" e a resposta não
   traz alerta.
3. **Given** um lote de dois frascos com um já recebido, **When** Thiago
   registra o segundo em ordem, **Then** o recebimento do laboratório conclui,
   a tarefa dele conclui e a resposta informa que o lote foi registrado e está
   liberado para os ensaios.
4. **Given** o recebimento do Lab A concluído, **When** alguém consulta a
   atividade, **Then** ela continua em andamento até o Lab B concluir ou ser
   dispensado.
5. **Given** um frasco já registrado, **When** Thiago tenta registrá-lo de
   novo, **Then** o registro é recusado e o primeiro continua valendo.

---

### User Story 4 - Bloquear registro incompleto ou inválido (Priority: P1)

Jornada 3. Na correria da bancada, Thiago esquece a temperatura ou o estado da
embalagem, ou digita letras na temperatura. O envio é recusado com a
indicação de cada campo com problema. Ele corrige e envia.

**Why this priority**: um registro incompleto quebra a rastreabilidade
regulatória do recebimento.

**Independent Test**: enviar o registro sem cada campo obrigatório e com
temperatura não numérica; conferir a recusa com os campos indicados e que o
frasco continua pendente; reenviar correto e conferir o aceite.

**Acceptance Scenarios**:

1. **Given** um frasco pendente, **When** Thiago envia sem temperatura,
   **Then** o envio é recusado, a resposta aponta o campo da temperatura e o
   frasco continua pendente.
2. **Given** um frasco pendente, **When** Thiago envia uma temperatura não
   numérica, **Then** o envio é recusado apontando o campo.
3. **Given** um frasco pendente, **When** Thiago envia sem o estado da
   embalagem, ou com um estado fora da lista, **Then** o envio é recusado
   apontando o campo.
4. **Given** um frasco pendente, **When** Thiago envia sem data e hora, ou com
   data e hora no futuro, **Then** o envio é recusado apontando o campo.
5. **Given** a recusa anterior, **When** Thiago corrige e envia de novo,
   **Then** o registro é aceito.

---

### User Story 5 - Só o próprio laboratório vê e registra os próprios frascos (Priority: P1)

Thiago tenta abrir os frascos de outro laboratório, pela lista, pelo código ou
pelo QR, e não encontra nada. Nenhuma resposta dada a ele traz nome químico,
CAS, fornecedor, SDS ou classificação de referência.

**Why this priority**: o vazamento de identidade ou de dados entre
laboratórios invalida o estudo (RF044, cegamento).

**Independent Test**: com dois laboratórios, a pessoa do Lab A tenta ler e
registrar um frasco do Lab B, pela lista e pelo código, e recebe "não
encontrado"; as respostas do Lab A não contêm os campos sigilosos.

**Acceptance Scenarios**:

1. **Given** a pessoa do Lab A, **When** lista os frascos do recebimento,
   **Then** os do Lab B não aparecem.
2. **Given** a pessoa do Lab A, **When** abre a visão cega de um frasco do
   Lab B pelo código, **Then** recebe "não encontrado", a mesma resposta de um
   código inexistente.
3. **Given** a pessoa do Lab A, **When** tenta registrar o recebimento de um
   frasco do Lab B, **Then** recebe "não encontrado" e nada é gravado.
4. **Given** a pessoa do Lab A, **When** abre a visão cega de um frasco do
   próprio laboratório, **Then** recebe código, lote, manuseio seguro,
   pictogramas, faixa térmica e dados do frasco, sem nome químico, CAS, SDS
   ou classificação de referência.
5. **Given** uma pessoa sem designação efetiva de laboratório participante no
   processo, **When** tenta listar ou registrar frascos, **Then** a ação é
   negada.

---

### User Story 6 - Registrar um frasco avariado ou com desvio térmico (Priority: P1)

Jornadas 2 e 4. Thiago abre a caixa: o gelo derreteu e o termômetro marca
21 °C para uma substância que pede 2 °C a 8 °C, ou o frasco trincou. Ele
registra o frasco com a temperatura real, o estado da embalagem e a
observação. A visão do frasco já trouxe a faixa esperada, então a tela pode
avisar antes do envio que a condição está fora do padrão. O sistema grava o
registro, abre uma inconformidade para o frasco, avisa o Grupo de Seleção por
tarefa e e-mail e responde com sucesso: o reporte foi registrado, a equipe
responsável foi avisada, o material deve ficar segregado e o recebimento do
laboratório aguarda a decisão. Ricardo recebe a tarefa "Resolver problemas no
recebimento de amostras" e o e-mail, e vê os dados informados por Thiago.

**Why this priority**: é a lacuna central da #71: hoje um problema no
recebimento não chega a ninguém.

**Independent Test**: registrar um frasco a 21 °C com faixa de 2 °C a 8 °C;
conferir a resposta de sucesso com a inconformidade, o recebimento do
laboratório ainda em andamento, a tarefa do Grupo de Seleção e o e-mail na
fila sem identidade química; entrar como Ricardo e ver os dados do registro.

**Acceptance Scenarios**:

1. **Given** um frasco com faixa de 2 °C a 8 °C, **When** Thiago registra
   21 °C com embalagem íntegra, **Then** o registro é salvo, a resposta é de
   sucesso, indica a inconformidade com o motivo "temperatura fora da faixa"
   e o frasco passa a "aguardando decisão".
2. **Given** um frasco qualquer, **When** Thiago registra a embalagem como
   avariada ou violada, **Then** o mesmo acontece, com o motivo
   correspondente.
3. **Given** uma substância sem faixa térmica (cadastrada antes desta
   entrega), **When** Thiago registra qualquer temperatura com embalagem
   íntegra, **Then** o frasco é recebido sem inconformidade.
4. **Given** um lote em que todos os outros frascos foram recebidos em ordem e
   um está aguardando decisão, **When** alguém consulta, **Then** o
   recebimento desse laboratório continua em andamento e a etapa seguinte dele
   não abre.
5. **Given** a inconformidade aberta, **When** o registro é salvo, **Then** o
   Grupo de Seleção do processo tem uma tarefa aberta de resolução e cada
   pessoa com designação efetiva no Grupo tem um e-mail na fila com o código
   do processo, o laboratório e o código cego, sem nome químico, CAS ou SDS.
6. **Given** uma segunda inconformidade, de outro frasco ou laboratório,
   enquanto a primeira está aberta, **When** é registrada, **Then** a mesma
   tarefa do Grupo continua aberta (não abre outra) e um novo e-mail vai para
   a fila.
7. **Given** o envio por e-mail não configurado na implantação, **When** a
   inconformidade é registrada, **Then** o registro e a tarefa são gravados e
   nenhum e-mail é pedido.
8. **Given** Ricardo, **When** lista as inconformidades do processo, **Then**
   vê cada uma com laboratório, código cego, substância, data e hora,
   temperatura, faixa esperada, estado da embalagem, observação, fotos e
   situação.
9. **Given** a pessoa do Lab B, **When** consulta os próprios frascos, as
   tarefas e a trilha, **Then** não vê a inconformidade do Lab A nem nada
   sobre ela.

---

### User Story 7 - Resolver a inconformidade: aceitar, reenviar ou desclassificar (Priority: P1)

Ricardo decide cada frasco com problema, sempre com justificativa:

- **Aceitar com ressalva**: o frasco passa a contar como recebido. Se era o
  que faltava, o recebimento do laboratório conclui.
- **Reenviar**: o sistema debita um frasco da reserva técnica da substância e
  gera um código cego novo para a mesma substância e o mesmo laboratório,
  ligado internamente ao código anterior. Ricardo imprime a etiqueta nova e
  despacha. Para o laboratório, o frasco novo aparece como mais um frasco
  pendente no mesmo recebimento; o registro do frasco anterior fica
  preservado.
- **Desclassificar**: o laboratório é dispensado na Etapa 3, com a
  justificativa como motivo. As outras inconformidades abertas dele são
  encerradas com a mesma decisão.

Quando não resta inconformidade aberta no processo, a tarefa de resolução do
Grupo conclui.

**Why this priority**: sem a decisão o laboratório afetado fica travado para
sempre.

**Independent Test**: com uma inconformidade aberta, reenviar; conferir o
código novo, a reserva debitada, o vínculo visível só ao Grupo, o frasco novo
pendente para o laboratório e a tarefa do Grupo concluída; registrar o frasco
novo em ordem e conferir o recebimento do laboratório concluído.

**Acceptance Scenarios**:

1. **Given** uma inconformidade aberta, **When** Ricardo decide sem
   justificativa ou com justificativa em branco, **Then** a decisão é recusada
   e nada muda.
2. **Given** o único frasco pendente de decisão de um laboratório cujos demais
   frascos foram recebidos, **When** Ricardo aceita com ressalva, **Then** o
   recebimento do laboratório conclui e a etapa seguinte dele fica liberada.
3. **Given** uma inconformidade aberta e reserva de 2 frascos, **When** Ricardo
   reenvia, **Then** a reserva passa a 1, um código novo existe para a mesma
   substância e laboratório, o código anterior deixa de ser ativo, a etiqueta
   nova aparece na lista de etiquetas e o recebimento do laboratório continua
   em andamento com o frasco novo pendente.
4. **Given** reserva zero, **When** Ricardo tenta reenviar, **Then** o
   reenvio é recusado, a inconformidade continua aberta e nada muda.
5. **Given** o reenvio feito, **When** Ricardo consulta a inconformidade,
   **Then** vê o código novo que substituiu o anterior.
6. **Given** o reenvio feito, **When** Thiago lista os frascos, **Then** vê o
   frasco anterior com a situação "substituído" e o frasco novo "pendente",
   e nada na resposta liga um ao outro.
7. **Given** o frasco novo, **When** Thiago o registra em ordem e era o único
   pendente, **Then** o recebimento do laboratório conclui.
8. **Given** uma inconformidade aberta, **When** Ricardo desclassifica,
   **Then** a execução do laboratório na Etapa 3 fica dispensada, as outras
   inconformidades abertas do laboratório são encerradas com a mesma decisão
   e os outros laboratórios não mudam.
9. **Given** uma inconformidade já decidida, **When** alguém tenta decidir de
   novo, **Then** a decisão é recusada.
10. **Given** a última inconformidade aberta do processo, **When** Ricardo a
    decide, **Then** a tarefa de resolução do Grupo conclui; uma
    inconformidade nova depois disso abre outra tarefa.
11. **Given** uma pessoa que não é do Grupo de Seleção do processo (inclusive
    o gestor, admin, BraCVAM e o laboratório), **When** tenta listar ou
    decidir inconformidades, **Then** a ação é negada.
12. **Given** a decisão tomada, **When** Thiago consulta o frasco, **Then** vê
    a situação resultante ("aceito com ressalva", "substituído" ou
    "desclassificado"), sem a justificativa de Ricardo.

---

### User Story 8 - Anexar fotos ao registro do frasco (Priority: P3)

Thiago fotografa o frasco trincado e anexa as imagens ao registro do frasco.
Ricardo vê as fotos ao analisar a inconformidade.

**Why this priority**: ajuda a decidir, mas a decisão é possível sem foto.

**Independent Test**: registrar um frasco, anexar uma imagem, baixá-la como
Lab A e como Grupo de Seleção, e tentar baixá-la como Lab B.

**Acceptance Scenarios**:

1. **Given** um frasco registrado pelo Lab A e o recebimento do Lab A em
   andamento, **When** Thiago anexa uma imagem PNG ou JPG, **Then** ela fica
   ligada ao registro e aparece na lista de fotos do frasco.
2. **Given** um arquivo de outro tipo ou acima do limite de tamanho, **When**
   Thiago anexa, **Then** o anexo é recusado.
3. **Given** a foto anexada, **When** Ricardo ou Thiago a baixam, **Then**
   recebem o arquivo; **When** a pessoa do Lab B tenta, **Then** recebe "não
   encontrado".
4. **Given** um frasco ainda não registrado, ou o recebimento do laboratório
   já concluído ou dispensado, **When** Thiago tenta anexar, **Then** o anexo
   é recusado.

### Edge Cases

- Registro feito por pessoa cuja designação deixou de ser efetiva (Spec 035):
  negado, como qualquer ação na execução do laboratório.
- Frasco de laboratório dispensado pelo gestor (Spec 036) antes do registro:
  o registro é recusado; a execução do laboratório já está resolvida.
- Dois registros simultâneos do mesmo frasco: só um vale; o outro recebe o
  conflito de frasco já registrado.
- Dois registros simultâneos dos dois últimos frascos do lote: o recebimento
  conclui uma vez só.
- Decisões simultâneas sobre a mesma inconformidade: só uma vale.
- Reenvios simultâneos com reserva 1: só um debita; o outro é recusado por
  reserva zero.
- Desclassificar um laboratório já dispensado pelo gestor: a inconformidade
  é encerrada como desclassificada sem nova dispensa.
- Processo encerrado, cancelado ou arquivado: registro, foto e decisão são
  recusados como qualquer alteração em processo imutável.
- Temperatura exatamente no limite da faixa: dentro da faixa.
- Inconformidade registrada antes da conclusão da definição das amostras: não
  ocorre, porque o recebimento só abre depois dela.
- Código novo do reenvio colidindo com código existente: o sistema gera outro,
  como na Spec 031.

## Requirements *(mandatory)*

### Functional Requirements

**Cadastro expandido (#72)**

- **FR-001**: O cadastro de substância DEVE exigir a classificação de
  referência, texto não vazio, ao criar a substância.
- **FR-002**: A alteração de substância DEVE recusar classificação de
  referência nula ou em branco quando enviada, e DEVE aceitar alterações que
  não a enviem, inclusive em substâncias sem ela.
- **FR-003**: O cadastro DEVE aceitar o regime de conservação: ambiente,
  refrigerado, congelado, ultracongelado ou personalizado, e as temperaturas
  mínima e máxima em °C.
- **FR-004**: Sem faixa informada, o regime ambiente DEVE gravar de 15 °C a
  25 °C e o refrigerado, de 2 °C a 8 °C. Os regimes congelado,
  ultracongelado e personalizado DEVEM exigir mínima e máxima. Faixa sem
  regime DEVE ser recusada.
- **FR-005**: O sistema DEVE recusar mínima maior que máxima, inclusive na
  alteração que mude só um dos limites.
- **FR-006**: O cadastro DEVE aceitar quantidade por frasco (positiva) com a
  unidade, tipo de recipiente, validade da alíquota e quantidade de frascos de
  reserva (inteiro não negativo, zero quando não informado).
- **FR-007**: O cadastro DEVE aceitar uma lista de pictogramas GHS, sem
  repetição, com valores de GHS01 a GHS09.
- **FR-008**: O lote de preparação continua sendo o campo de lote já
  existente; não há um segundo campo de lote.
- **FR-009**: A classificação de referência DEVE ser lida só pelo Grupo de
  Seleção de Amostras do processo e NÃO DEVE aparecer em nenhuma rota,
  etiqueta, evento ou e-mail acessível a outro cargo.
- **FR-010**: A visão cega do frasco e os dados de etiqueta DEVEM incluir
  pictogramas GHS, regime e faixa térmica, quantidade e unidade do frasco,
  tipo de recipiente e validade, e NÃO DEVEM incluir nome químico, CAS, SDS
  ou classificação de referência.
- **FR-011**: Substâncias cadastradas antes desta entrega DEVEM continuar
  válidas, com os campos novos vazios e reserva zero.

**Autopreenchimento (#72)**

- **FR-012**: O Grupo de Seleção DEVE poder consultar sugestões de dados de
  uma substância a partir do CAS, com o mesmo acesso das demais rotas de
  amostras.
- **FR-013**: A consulta DEVE validar o CAS antes de chamar a fonte externa.
- **FR-014**: A consulta DEVE devolver nome sugerido, pictogramas GHS
  sugeridos, o identificador do composto na fonte e o endereço público da
  página do composto, e NÃO DEVE gravar nada.
- **FR-015**: A consulta DEVE distinguir "composto não encontrado" de
  "consulta indisponível" (fonte fora do ar, erro ou tempo esgotado).
- **FR-016**: Os dados só DEVEM ser gravados quando o Grupo de Seleção enviar
  o cadastro ou a alteração com os valores que aceitou.

**Recebimento (#28)**

- **FR-017**: Os cinco templates DEVEM ter a Etapa 3 com a atividade por
  laboratório "Confirmação de Recebimento de Amostras", dependente da
  definição das amostras e editada pelo laboratório participante, e a
  atividade "Resolver problemas no recebimento de amostras", editada pelo
  Grupo de Seleção e aberta só por evento.
- **FR-018**: O laboratório participante DEVE poder listar os frascos do
  próprio laboratório no recebimento, com código, situação e, quando houver,
  o registro feito.
- **FR-019**: O laboratório participante DEVE poder abrir a visão cega de um
  frasco do próprio laboratório; para frasco de outro laboratório ou
  inexistente, a resposta DEVE ser "não encontrado".
- **FR-020**: O registro do frasco DEVE exigir data e hora de abertura (não
  futura), temperatura medida (numérica) e estado da embalagem (íntegra,
  avariada ou violada), e aceitar observação opcional.
- **FR-021**: O registro DEVE ser recusado com a indicação de cada campo
  inválido ou ausente, sem gravar nada.
- **FR-022**: Cada frasco DEVE ter no máximo um registro; o registro não pode
  ser alterado depois de salvo.
- **FR-023**: O registro DEVE ser aceito só enquanto o recebimento do
  laboratório estiver em andamento, e só por pessoa com designação efetiva
  pelo laboratório do frasco.
- **FR-024**: O frasco DEVE ser considerado em ordem quando a embalagem é
  íntegra e a temperatura está dentro da faixa da substância, limites
  incluídos. Sem faixa cadastrada, a temperatura não gera inconformidade.
- **FR-025**: Quando todo frasco ativo do laboratório tiver registro em ordem
  ou inconformidade aceita com ressalva, o recebimento do laboratório DEVE
  concluir, com a tarefa dele, e liberar a etapa seguinte do laboratório.
- **FR-026**: A resposta do registro DEVE dizer se o frasco ficou em ordem
  ou com inconformidade (e por quais motivos) e se o recebimento do
  laboratório concluiu ou aguarda decisão.

**Inconformidade e resolução (#71, #29)**

- **FR-027**: O registro fora de ordem DEVE abrir uma inconformidade para o
  frasco, com os motivos (temperatura fora da faixa, embalagem avariada,
  embalagem violada), na mesma operação do registro, e a resposta DEVE ser de
  sucesso, não de erro.
- **FR-028**: Com inconformidade aberta, o recebimento do laboratório NÃO
  DEVE concluir.
- **FR-029**: Ao abrir uma inconformidade, o sistema DEVE abrir a tarefa de
  resolução do Grupo de Seleção, se não houver uma aberta, e pedir um e-mail
  para cada pessoa com designação efetiva no Grupo de Seleção do processo,
  quando o envio por e-mail estiver configurado.
- **FR-030**: O e-mail DEVE trazer o código do processo, o nome do
  laboratório e o código cego, e NÃO DEVE trazer nome químico, CAS, SDS nem
  classificação de referência.
- **FR-031**: Só o Grupo de Seleção do processo DEVE listar inconformidades e
  decidir. A lista DEVE trazer laboratório, código cego, substância, o
  registro do frasco, a faixa esperada, as fotos, a situação, a decisão, a
  justificativa e o código que substituiu o frasco, quando houver.
- **FR-032**: A decisão DEVE ser uma de: aceitar com ressalva, reenviar ou
  desclassificar, sempre com justificativa não vazia. Inconformidade já
  decidida NÃO DEVE aceitar nova decisão.
- **FR-033**: "Aceitar com ressalva" DEVE fazer o frasco contar como recebido
  para o FR-025.
- **FR-034**: "Reenviar" DEVE debitar um frasco da reserva da substância,
  recusar quando a reserva for zero, desativar o código anterior, gerar um
  código novo para a mesma substância e laboratório e registrar que o novo
  substitui o anterior. O frasco novo DEVE aparecer como pendente no
  recebimento em andamento do laboratório, e o registro do frasco anterior
  DEVE ficar preservado.
- **FR-035**: "Desclassificar" DEVE dispensar o laboratório na Etapa 3, com a
  justificativa como motivo, e encerrar com a mesma decisão as outras
  inconformidades abertas do laboratório. Se o laboratório já estiver
  dispensado, só encerra as inconformidades.
- **FR-036**: Quando não restar inconformidade aberta no processo, a tarefa
  de resolução DEVE concluir.
- **FR-037**: O laboratório DEVE ver a situação dos próprios frascos
  (pendente, recebido, aguardando decisão, aceito com ressalva, substituído,
  desclassificado) e NÃO DEVE ver a justificativa da decisão nem o vínculo
  entre código novo e anterior.

**Fotos**

- **FR-038**: O laboratório DEVE poder anexar imagens PNG ou JPG, dentro do
  limite de tamanho dos anexos, ao registro de um frasco próprio enquanto o
  recebimento do laboratório estiver em andamento.
- **FR-039**: As fotos DEVEM ser baixadas só pelo laboratório do frasco e
  pelo Grupo de Seleção; para os demais, "não encontrado" ou negado.

**Jornadas do usuário (2026-10-04)**

- **FR-043**: Cada inconformidade, na lista do Grupo de Seleção, DEVE trazer
  o texto de alerta "Alerta de Recebimento: o laboratório {nome} registrou
  desvio {térmico | físico | térmico e físico} no frasco {código}."
- **FR-044**: O laboratório DEVE poder pré-verificar o registro de um frasco
  com os mesmos campos e recusas do registro e receber se ficaria em ordem,
  os motivos e uma mensagem de aviso, sem gravar registro, inconformidade,
  evento nem aviso.
- **FR-045**: A lista de frascos do laboratório DEVE trazer, em cada frasco,
  o lote, as instruções de manuseio seguro e os dados de conservação da
  FR-010, sem identidade química.
- **FR-046**: A lista de frascos do laboratório DEVE aceitar busca por trecho
  do código, sem diferenciar maiúsculas, restrita aos frascos dos
  laboratórios do usuário.

**Isolamento e auditoria**

- **FR-040**: Nenhuma resposta, evento ou e-mail acessível ao laboratório
  participante DEVE conter nome químico, CAS, SDS, classificação de
  referência ou dados de frascos de outro laboratório.
- **FR-041**: O sistema DEVE gravar na trilha o registro do frasco, a
  abertura da inconformidade, o anexo de foto, a decisão e o reenvio, com
  identificadores e contagens, sem nome químico, CAS, lote, código cego nem
  justificativa.
- **FR-042**: Os eventos de registro e de foto DEVEM seguir o isolamento por
  laboratório da Spec 037 (visíveis ao próprio laboratório e à gestão).

### Key Entities

- **Substância do estudo** (existente, ampliada): ganha classificação de
  referência, regime e faixa térmica, quantidade e unidade por frasco, tipo
  de recipiente, validade, reserva técnica e pictogramas GHS.
- **Frasco (código cego)** (existente, ampliado): ganha a referência ao
  código que ele substitui, quando nasce de um reenvio.
- **Registro de recebimento do frasco**: um por frasco; laboratório, execução
  do recebimento, data e hora de abertura, temperatura, estado da embalagem,
  observação, se ficou em ordem e os motivos da inconformidade.
- **Foto do registro**: imagem anexada a um registro de recebimento.
- **Inconformidade**: uma por registro fora de ordem; situação (aberta ou
  decidida), decisão, justificativa, quem decidiu e quando, e o código novo
  quando a decisão é reenviar.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos testes de isolamento, uma pessoa de laboratório não
  obtém dado de frasco de outro laboratório nem nome químico, CAS, SDS ou
  classificação de referência.
- **SC-002**: Todo registro fora de ordem gera, na mesma operação, uma
  inconformidade e uma tarefa aberta do Grupo de Seleção; nenhum fica sem
  aviso.
- **SC-003**: O analista registra um frasco em ordem com uma única operação
  de envio e recebe a conclusão do lote no envio do último frasco.
- **SC-004**: Nenhum recebimento de laboratório conclui com inconformidade
  aberta, verificado nos cenários de aceite, reenvio e desclassificação.
- **SC-005**: Todo reenvio deixa rastreável, para o Grupo de Seleção, qual
  código substituiu qual, e debita exatamente um frasco da reserva.
- **SC-006**: A consulta de sugestões por CAS não grava nenhum dado em 100%
  dos casos, inclusive quando a fonte responde.

## Assumptions

- Registro por frasco, um envio por frasco. O lote conclui sozinho no último
  frasco em ordem; não há botão separado de "concluir recebimento".
- O registro do frasco não é editável. Um erro de digitação que gere
  inconformidade é resolvido pelo Grupo de Seleção (aceitar com ressalva).
- A tarefa do laboratório continua aberta enquanto o recebimento aguarda
  decisão; a situação "aguardando decisão" aparece nos frascos.
- O reenvio não abre execução nova do laboratório, ao contrário do texto da
  issue #71: a execução do recebimento ainda está em andamento quando a
  inconformidade existe (ela não pode concluir), então o frasco novo entra
  nela como pendente. O histórico fica preservado no registro do frasco
  anterior.
- A desclassificação dispensa o laboratório na fase inteira (Spec 036), não
  só a substância.
- O e-mail não traz link: o frontend ainda não tem endereço configurável para
  a tela de inconformidades.
- A consulta ao PubChem envia o CAS à fonte pública. O CAS sozinho não revela
  o desenho do estudo, e quem consulta é o Grupo de Seleção.
- A consulta não sugere instruções de manuseio nem classificação de
  referência: são decisões do Grupo de Seleção.
- A devolução e o descarte (#31), o registro de despacho (RF039) e o painel de
  monitoramento interlaboratorial (RF046) ficam fora desta entrega.
- A leitura do gabarito pelo Grupo Gestor e pelo Estatístico fica para a
  Etapa 4.

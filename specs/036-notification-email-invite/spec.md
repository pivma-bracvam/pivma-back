# Feature Specification: Base de notificações e envio do convite por e-mail

**Feature Branch**: `feat/036-notification-email-invite`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: issue #49, "[E2-02a] Base de notificações + envio
do convite por e-mail". Criar uma base de notificações reutilizável, com o
e-mail como primeiro canal, e aplicá-la ao convite de designação da Spec 028.
O código de negócio pede o envio sem saber o canal nem o provedor. O pedido é
registrado junto com a mudança de negócio e enviado fora da requisição, com
novas tentativas. O provedor de e-mail é trocável por configuração. A falha de
envio não bloqueia o convite. O link bruto do convite não fica legível no
banco nem nos logs. WhatsApp (#50), Telegram (#51) e preferências do usuário
(#66) ficam fora.

## Contexto

- **CONFIRMADO, implementação atual**: a Spec 028 entregou o convite de
  designação com distribuição manual. O sistema devolve o token bruto só na
  resposta de criação e de reenvio; quem criou monta o link e compartilha por
  fora da plataforma (FR-006 da Spec 028).
- **CONFIRMADO, implementação atual**: o convite registra um canal
  pretendido, hoje com um único valor, `link`. A Spec 028 (FR-007) exigiu que
  novos canais pudessem entrar sem quebrar convites existentes.
- **CONFIRMADO, implementação atual**: o banco guarda só o hash do token do
  convite, nunca o valor bruto (Spec 028, research R1).
- **CONFIRMADO, implementação atual**: o sistema não envia nenhuma mensagem
  hoje. O trabalho fora da requisição usa o mecanismo embutido do framework
  web, que roda no mesmo processo da API e não tem nova tentativa nem
  garantia após reinício.
- **CONFIRMADO, implementação atual**: o provedor de IA já é escolhido por
  configuração, com uma implementação falsa para testes (Spec 013). Esta spec
  segue o mesmo princípio para os canais de mensagem.
- **CONFIRMADO, decisão do usuário (2026-10-01)**: o envio de e-mail não pode
  ficar preso a um provedor; o sistema só envia mensagens, não recebe; WhatsApp,
  Telegram e preferências do usuário são entregas separadas (#50, #51, #66).
- **CONFIRMADO, fonte oficial**: o Plano de Trabalho não tem requisito
  específico de notificação por e-mail. A entrega vem da issue #49 e da
  Spec 028 (FR-006, FR-007, Out of Scope).

Outras entregas previstas vão usar a mesma base: aviso de tarefa atrasada,
recuperação de senha (#45), comprovante de assinatura e aviso de relatório
pronto. Elas não fazem parte desta spec.

## Clarifications

### Session 2026-10-01

- Q: Qual é o caminho da página de aceite de convite no frontend? → A: O
  modelo do endereço inteiro é configurável na implantação, com um marcador
  para o token. O frontend ainda não implementou a página de convite, então o
  backend não fixa caminho (FR-018, FR-019).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convite chega por e-mail sem cópia manual (Priority: P1)

A pessoa responsável pela atribuição de cargo cria um convite, escolhe o canal
e-mail e informa o endereço. Sem nenhuma outra ação, a pessoa convidada recebe
um e-mail com o link de aceite e o prazo de validade. O link funciona como o
link manual da Spec 028.

**Why this priority**: é o objetivo da issue #49 e o primeiro uso real da
base de notificações. Sem ele, nada da base é exercitado de ponta a ponta.

**Independent Test**: criar um convite com canal e-mail para um endereço sem
conta, conferir que uma mensagem chega a esse endereço com o link e o prazo,
abrir o link e concluir o aceite pelo fluxo da Spec 028.

**Acceptance Scenarios**:

1. **Given** uma pessoa autorizada a convidar para um papel, **When** ela cria
   um convite com canal e-mail, **Then** o convite é criado como na Spec 028 e
   uma mensagem é enviada ao e-mail do convite, com o link de aceite, o papel,
   o processo e o prazo de validade.
2. **Given** um convite com canal e-mail ainda pendente, **When** a pessoa
   responsável o reenvia, **Then** uma nova mensagem é enviada com o novo link
   e o novo prazo, e o link anterior deixa de valer (regra da Spec 028).
3. **Given** um convite com canal e-mail, **When** ele é criado, **Then** a
   resposta continua trazendo o token, para que a pessoa possa compartilhar o
   link manualmente se quiser.
4. **Given** um convite com canal `link`, **When** ele é criado ou reenviado,
   **Then** nenhuma mensagem é enviada e o comportamento é idêntico ao atual.

---

### User Story 2 - Falha de envio não trava o convite e fica visível (Priority: P1)

O serviço de e-mail pode estar fora do ar, recusar o endereço ou demorar. O
convite não pode depender disso. A pessoa que criou o convite precisa saber se
a mensagem saiu, para decidir se compartilha o link manualmente.

**Why this priority**: é critério de aceite explícito da issue #49 e da
proposta original do canal (o link continua válido mesmo se o envio falhar).
Sem isso, uma falha externa bloquearia a atribuição de cargo.

**Independent Test**: com o serviço de e-mail indisponível, criar um convite
com canal e-mail; conferir que a criação responde com sucesso, que o envio é
tentado de novo e que a listagem de convites mostra a situação do envio até
ficar como falho.

**Acceptance Scenarios**:

1. **Given** o serviço de e-mail indisponível, **When** um convite com canal
   e-mail é criado, **Then** a criação conclui com sucesso, o token é
   devolvido e o link funciona.
2. **Given** um envio que falhou por erro temporário, **When** o serviço volta
   antes de esgotar as tentativas, **Then** a mensagem é enviada e a situação
   passa a enviado.
3. **Given** um envio que esgotou as tentativas, **When** a pessoa responsável
   lista os convites do processo, **Then** vê a situação do envio como falho.
4. **Given** um convite com envio pendente, **When** a pessoa lista os
   convites, **Then** vê a situação do envio como pendente.
5. **Given** um envio pendente de um convite que foi revogado ou reenviado,
   **When** chega a hora de enviar, **Then** a mensagem antiga não é enviada.

---

### User Story 3 - Base reutilizável e provedor trocável (Priority: P2)

Quem desenvolve uma próxima funcionalidade (aviso de atraso, recuperação de
senha, comprovante) pede um envio informando o tipo de aviso, o destinatário e
os dados da mensagem, sem tratar canal, provedor, fila ou novas tentativas. A
equipe troca o provedor de e-mail mudando só a configuração da implantação.

**Why this priority**: é o que evita repetir o envio em cada funcionalidade e
ficar preso a um provedor. Não entrega valor visível ao usuário final sozinha,
por isso vem depois das histórias do convite.

**Independent Test**: com o canal configurado como falso, pedir um envio a
partir de um teste e conferir que a mensagem registrada tem o destinatário e o
conteúdo esperados; trocar a configuração para um servidor de e-mail de
desenvolvimento e conferir que a mesma mensagem chega lá, sem mudar código.

**Acceptance Scenarios**:

1. **Given** uma operação de negócio que pede um envio, **When** a operação é
   desfeita por erro antes de ser confirmada, **Then** nenhum envio é
   registrado nem enviado.
2. **Given** uma operação de negócio que pede um envio, **When** a operação é
   confirmada, **Then** o envio fica registrado e é processado mesmo que a API
   reinicie em seguida.
3. **Given** dois provedores de e-mail compatíveis, **When** a equipe troca a
   configuração de um para o outro, **Then** os envios seguintes saem pelo novo
   provedor sem mudança de código.
4. **Given** a configuração de canal falso, **When** um envio é processado,
   **Then** nenhuma rede é usada e a mensagem fica disponível para conferência.

---

### Edge Cases

- **Convite expira antes do envio**: o prazo padrão do convite é de 1 hora.
  Se as tentativas ainda não tiveram sucesso quando o convite expira, o envio
  para de ser tentado e fica marcado como falho, com o motivo; enviar um link
  vencido não tem utilidade.
- **Revogação com envio pendente**: o envio pendente é cancelado e não sai.
- **Reenvio com envio pendente ou falho**: o envio anterior é cancelado e um
  novo envio é registrado com o novo link. A situação mostrada passa a ser a
  do envio mais recente.
- **Endereço recusado pelo provedor** (erro permanente, por exemplo endereço
  inexistente): o envio fica falho sem novas tentativas.
- **Dois processos de envio ao mesmo tempo**: a mesma mensagem não pode sair
  duas vezes por conta disso.
- **Processo de envio parado**: os envios ficam pendentes e saem quando ele
  voltar, desde que o convite ainda seja válido.
- **Canal de e-mail não configurado na implantação**: criar convite com canal
  e-mail é recusado com mensagem clara, e o canal `link` continua disponível.
- **Logs e trilha de auditoria**: não registram o link nem o token bruto,
  inclusive em mensagens de erro do provedor.

## Requirements *(mandatory)*

### Functional Requirements

**Base de notificações**

- **FR-001**: O sistema DEVE oferecer um ponto único para o código de negócio
  pedir um envio, informando o tipo de aviso, o destinatário e os dados da
  mensagem, sem escolher provedor.
- **FR-002**: O pedido de envio DEVE ser registrado na mesma transação da
  operação de negócio que o originou. Se a operação for desfeita, o pedido não
  existe.
- **FR-003**: O envio DEVE acontecer fora da requisição que o originou, num
  processo separado da API, e DEVE sobreviver a reinícios da API e do próprio
  processo de envio.
- **FR-004**: Um envio que falha por erro temporário DEVE ser tentado de novo,
  com intervalos crescentes, até um limite configurável. Esgotado o limite, ou
  diante de erro permanente, o envio DEVE ficar marcado como falho, com o
  motivo.
- **FR-005**: Cada envio DEVE ter uma situação consultável: pendente,
  enviado, falho ou cancelado, com a data da última tentativa e o número de
  tentativas.
- **FR-006**: A mesma mensagem NÃO DEVE ser enviada duas vezes por causa de
  processos de envio concorrentes ou de reprocessamento após falha.
- **FR-007**: O canal de envio DEVE ser escolhido por configuração da
  implantação. DEVE existir um canal falso, sem rede, que guarda as mensagens
  para conferência em testes e desenvolvimento.
- **FR-008**: O canal de e-mail DEVE usar um protocolo padrão aceito pela
  maioria dos provedores, de forma que trocar de provedor exija apenas mudar a
  configuração (servidor, porta, credenciais, remetente).
- **FR-009**: Conteúdo sensível de um envio (como o link do convite) NÃO DEVE
  ficar legível no banco e DEVE deixar de existir depois que o envio termina
  (enviado, falho ou cancelado).
- **FR-010**: Logs, trilha de auditoria e mensagens de erro NÃO DEVEM conter o
  conteúdo sensível de um envio.

**Convite por e-mail**

- **FR-011**: O convite DEVE aceitar o canal `email`, além de `link`.
  Convites existentes continuam com `link`.
- **FR-012**: Criar um convite com canal `email` DEVE registrar um envio para
  o e-mail do convite, com o link de aceite, o papel, o processo e o prazo de
  validade.
- **FR-013**: Reenviar um convite com canal `email` DEVE cancelar o envio
  anterior ainda não concluído e registrar um novo envio com o novo link e o
  novo prazo.
- **FR-014**: Revogar um convite DEVE cancelar o envio ainda não concluído.
- **FR-015**: Um envio de convite NÃO DEVE sair depois que o convite expirou,
  foi revogado, aceito ou reenviado; nesses casos fica cancelado ou falho, com
  o motivo.
- **FR-016**: A criação e o reenvio do convite DEVEM concluir com sucesso
  independentemente do resultado do envio, e a resposta DEVE continuar
  trazendo o token, como na Spec 028.
- **FR-017**: A listagem e a consulta de convites DEVEM mostrar a situação do
  envio mais recente de cada convite com canal `email`, para quem já pode ver
  o convite pela Spec 028.
- **FR-018**: O link enviado DEVE ser montado a partir de um modelo de
  endereço completo configurado na implantação, com um marcador para o token
  (por exemplo, `https://<frontend>/convites/{token}`). O backend não fixa
  nenhum caminho do frontend.
- **FR-019**: Se o canal de e-mail ou o modelo de endereço do convite não
  estiverem configurados na implantação, o sistema DEVE recusar a criação de
  convite com canal `email`, com mensagem clara, sem afetar o canal `link`.
- **FR-020**: Todas as regras da Spec 028 (autorização, expiração, reenvio,
  revogação, aceite, encerramento da etapa) DEVEM continuar iguais.
- **FR-021**: A trilha de auditoria DEVE registrar o resultado final de cada
  envio de convite (enviado, falho ou cancelado), sem o link.

### Key Entities

- **Envio (notificação)**: um pedido de mensagem para um destinatário por um
  canal. Guarda o tipo de aviso, o canal, o destinatário, a referência ao
  objeto de negócio que o originou (por exemplo, o convite), a situação, o
  número de tentativas, a data da próxima tentativa, o motivo da falha e o
  conteúdo protegido enquanto o envio não termina.
- **Convite de designação** (Spec 028): passa a aceitar o canal `email` e
  passa a expor a situação do envio mais recente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos convites criados com canal e-mail com o serviço de
  e-mail disponível, a mensagem chega ao endereço do convite em até 1 minuto.
- **SC-002**: Em 100% das criações de convite com o serviço de e-mail
  indisponível, a criação conclui com sucesso e o link funciona.
- **SC-003**: Nenhuma mensagem é enviada para convite revogado, aceito,
  expirado ou com link substituído por reenvio.
- **SC-004**: Nenhuma mensagem sai em duplicidade, mesmo com dois processos de
  envio rodando ao mesmo tempo.
- **SC-005**: O link do convite não aparece em nenhum registro do banco depois
  que o envio termina, nem em nenhum log ou evento de auditoria.
- **SC-006**: Trocar de provedor de e-mail exige zero mudanças de código.
- **SC-007**: Convites com canal `link` mantêm 100% do comportamento atual.

## Assumptions

- O e-mail é enviado em português, com texto simples e uma versão formatada,
  identificando o processo, o papel, o prazo de validade e o link.
- O remetente é um endereço de "não responda" configurado na implantação. O
  sistema não recebe respostas.
- Limite padrão de tentativas: 5, com intervalos crescentes, sempre limitado
  pelo prazo do convite. Os valores são configuráveis.
- O reenvio usa o canal já gravado no convite. Trocar o canal de um convite
  existente fica fora do escopo.
- A situação do envio é vista por quem já pode listar os convites do processo
  (Spec 028). Não existe reenvio só da mensagem: para mandar de novo, usa-se o
  reenvio do convite, que gera link novo.
- A implantação passa a rodar um segundo processo, o de envio, além da API. Em
  desenvolvimento, um servidor de e-mail falso com tela web mostra as
  mensagens enviadas.
- A escolha do provedor de produção e a configuração do domínio de envio
  (SPF, DKIM, DMARC) são decisões de infraestrutura fora desta spec.
- Preferências de notificação (#66), WhatsApp (#50), Telegram (#51), aviso de
  tarefa atrasada, relatórios e assinatura ficam fora do escopo.

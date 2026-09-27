# Feature Specification: Formato único das respostas de erro

**Feature Branch**: `feat/034-error-response-standard`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Spec 034: padronizar as respostas de erro da API num formato único com código estável e mensagem, incluindo os 422 de validação, conforme alinhado em 2026-09-27 (Specs 032–034, entrega única ao frontend)."

## Contexto

As Specs 032 e 033 padronizaram as listagens e as referências. Esta é a última das três: padroniza as respostas de erro, que também ficam mais caras de mudar com o tempo. O frontend recebe as três specs juntas, num único changelog, e usa deploy direto da `develop`, onde a quebra temporária foi aceita.

Hoje o frontend precisa tratar pelo menos quatro formatos de erro:

- `detail` como texto livre, em cerca de 60 pontos. As mensagens misturam inglês ("User not found", "Forbidden", "Invalid credentials") e português ("Processo não encontrado."). Muitas repetem a mensagem interna de uma exceção.
- `detail` como objeto `{code, message}`, em 19 pontos, com uns 8 códigos (`invalid_transition`, `forbidden`, `not_found`, `form_submitted`, `invalid_form_values` e os das amostras cegas: `invalid_cas`, `duplicate_cas`, `missing_sds`...).
- Validação de entrada (`422`): uma lista de erros por campo no formato do framework, que repete o valor enviado. Só o campo de senha é tratado à parte, com uma mensagem fixa.
- Rota inexistente (`404`), método não permitido (`405`) e erro inesperado (`500`), no formato do framework.

Sem um código estável, o frontend só consegue decidir o que mostrar comparando textos, que mudam sem aviso.

## Clarifications

### Session 2026-09-27

Decisões da conversa de alinhamento (valem para as Specs 032–034):

- Q: Padronizar os erros agora, mesmo quebrando contratos? → A: Sim, junto com as listagens e as referências, numa entrega só ao frontend.
- Q: Qual é a forma do corpo de erro? → A: A chave `detail` continua, sempre com um objeto `{code, message, fields}`; `fields` só aparece em erros de validação.
- Q: Em que idioma ficam as mensagens? → A: Tudo em português, inclusive as mensagens por campo da validação, traduzidas por tipo de erro; tipos sem tradução usam uma mensagem genérica em português. Os códigos ficam em inglês.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Decidir pelo código, não pelo texto (Priority: P1)

O frontend trata qualquer erro da API da mesma forma: lê um código estável para decidir o comportamento (redirecionar para o login, mostrar "sem permissão", marcar um campo, avisar que o registro mudou) e usa a mensagem para exibir. Isso vale para todos os pontos da API, inclusive os erros do próprio framework.

**Why this priority**: É o objetivo da padronização. Enquanto um erro sair em outro formato, o frontend mantém um tratamento especial para ele.

**Independent Test**: Provocar um erro de cada classe (sem sessão, sem permissão, inexistente, conflito, validação, origem não confiável, rota inexistente, método não permitido, falha inesperada) e verificar que todas as respostas têm o mesmo formato, com código e mensagem preenchidos.

**Acceptance Scenarios**:

1. **Given** uma requisição sem sessão a uma rota protegida, **When** a API responde, **Then** o erro vem no formato único com o código de "não autenticado".
2. **Given** um usuário sem permissão, **When** tenta uma ação proibida, **Then** o erro vem no formato único com o código de "proibido".
3. **Given** um recurso inexistente ou invisível, **When** o usuário o consulta, **Then** o erro vem no formato único com o código de "não encontrado", sem revelar se o recurso existe.
4. **Given** uma regra de negócio violada que já tem código próprio (ex.: transição inválida, CAS duplicado), **When** a API recusa, **Then** o código continua o mesmo de hoje.
5. **Given** uma rota inexistente ou um método não permitido, **When** a API responde, **Then** o erro vem no formato único.
6. **Given** uma falha inesperada no servidor, **When** a API responde, **Then** o erro vem no formato único, com código genérico e sem detalhes internos.

---

### User Story 2 - Erros de validação apontam os campos (Priority: P1)

Ao enviar um formulário inválido, o frontend recebe, além do código geral de validação, a lista dos campos com problema: o caminho de cada campo, um código do problema e uma mensagem. Assim marca cada campo sem interpretar texto.

**Why this priority**: Os formulários são a principal fonte de erros visíveis ao usuário. Hoje o formato é o do framework e repete o valor enviado.

**Independent Test**: Enviar um cadastro com dois campos inválidos e verificar que a resposta traz o código de validação e uma entrada por campo, com caminho, código e mensagem, sem o valor enviado.

**Acceptance Scenarios**:

1. **Given** um cadastro com e-mail inválido e nome vazio, **When** a API recusa, **Then** a resposta traz o código de validação e dois itens por campo, um para `email` e um para `full_name`.
2. **Given** um parâmetro de consulta inválido (ex.: `per_page=101`), **When** a API recusa, **Then** o item do campo indica que o problema está no parâmetro de consulta `per_page`.
3. **Given** uma senha inválida, **When** a API recusa, **Then** a resposta não traz o valor enviado nem detalhes da regra de senha além do código e da mensagem genéricos, como já acontece hoje.
4. **Given** qualquer erro de validação, **When** a API responde, **Then** nenhum valor enviado pelo usuário é repetido na resposta.
5. **Given** um erro de regra de negócio sobre um campo específico (ex.: CAS inválido), **When** a API recusa, **Then** ele usa o mesmo formato, com o código específico.

---

### User Story 3 - Códigos documentados (Priority: P2)

Quem consome a API encontra na documentação interativa o formato do erro e, em cada rota, os códigos de status possíveis com esse formato. A lista de códigos genéricos está descrita.

**Why this priority**: O changelog manda o frontend conferir os formatos na documentação.

**Independent Test**: A documentação descreve o schema de erro e o associa às respostas de erro das rotas.

**Acceptance Scenarios**:

1. **Given** a documentação da API, **When** alguém consulta o schema de erro, **Then** vê código, mensagem e lista de campos, com descrição em cada item.
2. **Given** a documentação da API, **When** alguém consulta uma rota, **Then** as respostas de erro de validação apontam para o schema padrão, não para o do framework.

---

### Edge Cases

- Erro levantado por dependências comuns a todas as rotas (sessão, origem confiável): formato único.
- Exceção de domínio convertida em erro HTTP repetindo a mensagem interna: passa a ter código próprio e mensagem pensada para o usuário, sem detalhes internos (nomes de tabela, identificadores de constraint, stack).
- Erro de anexo (arquivo vazio, grande demais, extensão não permitida): mantém os códigos de status atuais (`400`, `413`, `422`) e os códigos `empty_file`, `file_too_large`, `extension_not_allowed`.
- Serviço de IA indisponível (`503`): formato único, com código próprio.
- Erro sem código específico no domínio: usa o código genérico do status.
- Resposta de erro com cabeçalhos exigidos pelo protocolo (ex.: autenticação): os cabeçalhos continuam.
- Tipo de erro de validação sem tradução: mensagem genérica em português ("Valor inválido."), com o código do tipo preservado.

## Requirements *(mandatory)*

### Functional Requirements

**Formato**

- **FR-001**: Toda resposta de erro da API (status 4xx e 5xx) DEVE ter o corpo `{"detail": {"code": ..., "message": ...}}`, com um código estável e uma mensagem. Em erros de validação, o objeto traz também `fields`.
- **FR-002**: O código DEVE ser um identificador curto, em inglês, minúsculo e separado por sublinhado, estável entre versões. Mudar um código é mudança de contrato.
- **FR-003**: Os erros de validação de entrada DEVEM trazer, além do código geral, a lista dos campos com problema: onde está o campo (corpo, parâmetro de consulta, caminho, cabeçalho), o caminho do campo, um código do problema e uma mensagem.
- **FR-012**: Todas as mensagens DEVEM estar em português, inclusive as mensagens por campo da validação. Tipos de erro de validação sem tradução específica DEVEM usar uma mensagem genérica em português.
- **FR-004**: Nenhuma resposta de erro DEVE repetir valores enviados pelo usuário nem detalhes internos (mensagens de exceção de banco, stack, nomes internos).
- **FR-005**: Os códigos específicos que já existem (`invalid_transition`, `forbidden`, `not_found`, `form_submitted`, `invalid_form_values`, `not_a_file_field`, `empty_file`, `file_too_large`, `extension_not_allowed`, `invalid_cas`, `duplicate_cas`, `no_substances`, `missing_sds`, `no_laboratories`) DEVEM continuar com o mesmo nome e significado.
- **FR-006**: Cada status sem código específico DEVE ter um código genérico: não autenticado (`401`), proibido (`403`), não encontrado (`404`), método não permitido (`405`), conflito (`409`), validação (`422`), serviço indisponível (`503`), erro interno (`500`), e os demais status usados hoje (`400`, `413`).
- **FR-007**: Os erros com texto livre hoje DEVEM ganhar um código que distinga os casos que o frontend precisa tratar de forma diferente no mesmo status. Exemplos: credenciais inválidas, origem não confiável, conta desativada, desativar a si mesmo, último administrador, convite com e-mail diferente, convite expirado.

**Comportamento preservado**

- **FR-008**: Os códigos de status HTTP de cada situação NÃO DEVEM mudar.
- **FR-009**: As regras de acesso NÃO DEVEM mudar: onde hoje a API responde `404` para não revelar um recurso, continua respondendo `404`, sem pista no código ou na mensagem.
- **FR-010**: O tratamento da senha em validação continua: a resposta não expõe a regra nem o valor enviado.

**Documentação**

- **FR-011**: O schema de erro DEVE aparecer na documentação da API, com descrição em cada campo, e as respostas de validação das rotas DEVEM apontar para ele.

### Key Entities

- **Erro**: código estável, mensagem e, em validação, lista de campos.
- **Erro de campo**: origem (corpo, consulta, caminho, cabeçalho), caminho do campo, código do problema e mensagem.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das respostas de erro da API seguem o formato único, verificado para cada status usado (400, 401, 403, 404, 405, 409, 413, 422, 500, 503).
- **SC-002**: O frontend decide o tratamento de qualquer erro só pelo código, sem comparar mensagens.
- **SC-003**: Nenhuma resposta de erro repete valores enviados pelo usuário, verificado nos erros de validação com senha, e-mail e campos de texto.
- **SC-004**: Os 14 códigos específicos existentes continuam com o mesmo nome.
- **SC-005**: Nenhum código de status HTTP muda em relação a antes da padronização.
- **SC-006**: Nenhuma mensagem de erro sai em inglês, verificado para os erros de validação mais comuns (campo obrigatório, formato de e-mail, tamanho, limite numérico, valor fora da lista) e para os erros genéricos por status.

## Assumptions

- Os códigos ficam em inglês e as mensagens, em português, são pensadas para o usuário final. O frontend pode trocar a mensagem pela sua própria a partir do código.
- A lista de códigos genéricos por status é fechada e documentada; os códigos específicos crescem conforme o domínio precisar.
- Os códigos por campo da validação usam os tipos de erro que o framework já produz (ex.: campo obrigatório ausente, formato inválido, valor acima do máximo), com nomes estáveis.
- Não há identificador de rastreio (`request_id`) nem bloco de metadados no erro nesta entrega; pode entrar depois sem quebrar o formato.
- Os logs administrativos, fora da documentação desde a Spec 033, também passam a responder erros no formato único, mas não entram no changelog.
- A mudança quebra o contrato de todas as respostas de erro. Vai para o changelog único das Specs 032–034.

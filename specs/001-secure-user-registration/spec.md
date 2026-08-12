# Feature Specification: Cadastro Seguro de Usuários

**Feature Branch**: `not-created`

**Created**: 2026-08-11

**Status**: Approved on 2026-08-12 by the feature requester

**Input**: User description: "Permitir o cadastro seguro de usuário com username, e-mail e
senha, preservando os contratos existentes compatíveis com a segurança necessária."

## Clarifications

### Session 2026-08-12 (redução de escopo)

**Contexto**: esta é a primeira feature da requisitante com Spec Kit. A sequência de clarifications
da Session 2026-08-11 produziu, isoladamente, respostas corretas, mas o conjunto resultou em uma
implementação com garantias de nível produção crítica (blocklist local de 100k senhas com
prontidão fail-closed, aborto de migração por inspeção de formato de credencial, reserva global de
identificador após exclusão lógica, gate de benchmark com aprovação formal) desproporcionais a um
projeto novo, sem usuários reais em produção e sem outro responsável técnico revisando o escopo. A
própria requisitante, única aprovadora da spec original, decidiu reduzir o escopo antes da
integração.

- Q: A blocklist local de senhas comuns/comprometidas (FR-008) e sua prontidão fail-closed
  (FR-024) devem continuar nesta versão? → A: Não. Adiadas para um backlog futuro; a v1 valida
  apenas tamanho e ausência de espaço em branco na senha (FR-007).
- Q: A migração deve continuar abortando ao encontrar uma credencial existente que não seja um
  hash Argon2id válido (parte de FR-022)? → A: Não. Como o projeto é novo e não há credenciais
  reais em produção, a migração deixa de inspecionar o formato da senha armazenada; ela apenas
  renomeia a coluna. A checagem de colisão de `lower(username)`/`lower(email)` entre usuários
  ativos é mantida, por ser barata e evitar um estado inconsistente com o novo índice.
- Q: Username e e-mail devem continuar reservados após a exclusão lógica de um usuário (FR-023)? →
  A: Não. Volta ao comportamento anterior à feature: a unicidade (agora case-insensitive) vale
  somente entre usuários ativos; um usuário excluído libera seu username e e-mail para reuso.
- Q: O benchmark do perfil Argon2id com aprovação formal antes da aceitação (SC-011) continua
  sendo um gate de entrega desta feature? → A: Não. Deixa de ser um critério de aceite formal desta
  versão; pode ser revisitado se houver indício de latência excessiva em uso real.

Essas quatro decisões substituem, nesta versão, os itens correspondentes da Session 2026-08-11
abaixo. O histórico da sessão original é preservado para rastreabilidade da decisão anterior.

### Session 2026-08-11

- Q: Após remover espaços externos, como username e e-mail devem ser armazenados e exibidos? → A:
  Preservar a caixa fornecida em ambos os campos.
- Q: Quando dois cadastros simultâneos usam o mesmo username ou e-mail, inclusive com variações de
  caixa, qual resultado o sistema deve garantir? → A: Exatamente um cadastro é criado; os demais
  retornam HTTP 409.
- Q: Quais valores devem ser aceitos como username além da regra de unicidade case-insensitive? →
  A: De 3 a 64 caracteres; letras ASCII, números, ponto, hífen e sublinhado; sem espaços.
- Q: Como o sistema deve tratar espaços e caracteres Unicode na senha antes de armazená-la? → A:
  Rejeitar qualquer caractere de espaço em branco e permitir os demais caracteres Unicode.
- Q: O cadastro deve rejeitar senhas conhecidas como comuns ou comprometidas, além das regras de
  comprimento e espaços? → A: Rejeitar senhas presentes em uma lista local versionada de senhas
  comuns ou comprometidas.
- Q: O que a migração deve fazer se encontrar usuários com senhas existentes que ainda não estejam
  protegidas por Argon2id? → A: Abortar a migração e exigir uma estratégia separada aprovada.
- Q: Depois que um usuário recebe exclusão lógica, o username e o e-mail dele devem continuar
  indisponíveis para novos cadastros? → A: Username e e-mail continuam reservados após exclusão
  lógica.
- Q: Qual resposta pública o cadastro deve retornar quando a senha estiver na lista local de
  bloqueio? → A: HTTP 422 com mensagem genérica de senha inválida.
- Q: Quantos pedidos simultâneos o teste mínimo de concorrência deve executar para cada caso de
  username e e-mail equivalentes? → A: Dois pedidos por caso; um retorna HTTP 201 e o outro HTTP
  409.
- Q: Qual critério deve autorizar o perfil Argon2id após medir latência e memória no container do
  projeto? → A: O responsável técnico da feature aprova explicitamente as medições registradas,
  sem limite numérico pré-fixado.
- Q: Como o serviço deve se recuperar quando a blocklist estiver ausente ou corrompida? → A:
  Bloquear a prontidão até restaurar o artefato íntegro e reiniciar ou reimplantar.

### Session 2026-08-12

- Q: Quem deve aprovar uma nova execução da migração abortada e qual regime operacional ela deve exigir? → A: A pessoa solicitante da feature aprova; exigir janela de manutenção e backup confirmado.
- Q: Qual faixa do `argon2-cffi` deve ser aprovada e quem responde por atualizá-la? → A: `>=25.1,<26`; a pessoa solicitante da feature revisa cada atualização.
- Q: Qual fonte deve gerar a blocklist local e quais registros devem acompanhar a aquisição? → A: Lista pública SecLists Top 100k fixada por commit; registrar data, checksums e termos na aquisição.
- Q: Em qual branch devemos implementar esta feature e para qual branch ela deverá seguir na integração? → A: Criar `feature/secure-user-registration` a partir de `main`; integrar em `main` por PR.
- Q: O rate limiting do endpoint público de cadastro deve fazer parte desta feature? → A: Fora
  desta feature; registrar como trabalho futuro separado.
- Q: Como o endpoint deve responder quando ocorrer uma falha interna inesperada durante o hashing,
  `flush` ou `commit`? → A: HTTP 500 genérico, rollback e nenhum detalhe interno ou segredo.
- Q: Qual corpo exato deve representar a mensagem genérica de senha inválida no HTTP 422? → A:
  `{"detail": "Invalid password"}`.
- Q: Quais valores os demais campos de auditoria devem ter imediatamente após o cadastro público?
  → A: `updated_at`, `updated_by`, `deleted_at` e `deleted_by` permanecem nulos.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concluir cadastro válido (Priority: P1)

Uma pessoa fornece username, e-mail e senha para criar seu cadastro no pi*VMA. Ao concluir, ela
recebe a identificação pública da conta sem qualquer representação da senha.

**Why this priority**: O cadastro é o resultado principal da feature e viabiliza a futura
autenticação prevista no RF001.

**Independent Test**: Enviar dados válidos para cadastro e verificar que uma única conta é criada,
que a confirmação contém id, username e e-mail e que nenhum campo de senha aparece.

**Acceptance Scenarios**:

1. **Given** que username e e-mail ainda não foram utilizados, **When** a pessoa envia username,
   e-mail e senha válidos, **Then** o sistema cria o usuário e retorna HTTP 201 com id, username e
   e-mail.
2. **Given** um cadastro concluído, **When** a resposta é examinada, **Then** ela não contém a senha
   fornecida, seu resumo seguro ou outra representação do segredo.
3. **Given** um cadastro concluído, **When** os dados persistidos são examinados por um teste
   autorizado, **Then** a senha original não está armazenada em formato recuperável por leitura
   direta.
4. **Given** um username fora do comprimento permitido ou com caractere não permitido, **When** a
   pessoa tenta se cadastrar, **Then** o sistema rejeita o pedido sem criar uma conta.
5. **Given** uma senha que contém um caractere de espaço em branco, **When** a pessoa tenta se
   cadastrar, **Then** o sistema rejeita o pedido sem alterar ou remover caracteres da senha, com
   HTTP 422 e `{"detail": "Invalid password"}`.

> **Cenário removido nesta versão** (ver Session 2026-08-12): rejeição de senha por lista local de
> bloqueio. Adiado para backlog; não faz parte do conjunto de validação atual.

---

### User Story 2 - Impedir identificadores duplicados (Priority: P2)

Uma pessoa não consegue criar outra conta usando username ou e-mail já utilizado, mesmo quando o
novo valor difere apenas por maiúsculas ou minúsculas. O sistema informa qual identificador causou
o conflito sem alterar a conta existente.

**Why this priority**: A unicidade evita contas ambíguas e preserva o contrato de conflito já
registrado pelos testes existentes.

**Independent Test**: Criar uma conta e repetir o cadastro com o mesmo username e o mesmo e-mail,
incluindo variações de maiúsculas e minúsculas, verificando HTTP 409 e ausência de uma nova conta
em todos os casos.

**Acceptance Scenarios**:

1. **Given** uma conta com determinado username, **When** outra pessoa tenta cadastrar esse
   username, **Then** o sistema retorna HTTP 409, identifica o conflito de username e não cria uma
   nova conta.
2. **Given** uma conta com determinado e-mail, **When** outra pessoa tenta cadastrar esse e-mail,
   **Then** o sistema retorna HTTP 409, identifica o conflito de e-mail e não cria uma nova conta.
3. **Given** uma conta com username e e-mail já utilizados, **When** ambos são reenviados, **Then**
   o sistema preserva a precedência atual e informa primeiro o conflito de username.
4. **Given** uma conta com determinado e-mail, **When** outra pessoa tenta cadastrar o mesmo
   e-mail com variação de maiúsculas ou minúsculas, **Then** o sistema retorna HTTP 409 e não cria
   uma nova conta.
5. **Given** uma conta com determinado username, **When** outra pessoa tenta cadastrar um username
   que difere apenas por maiúsculas ou minúsculas, **Then** o sistema retorna HTTP 409 e não cria
   uma nova conta.
6. **Given** dois pedidos simultâneos com o mesmo username ou com o mesmo e-mail, inclusive com
   variações de caixa, **When** o sistema processa cada caso, **Then** exatamente um pedido retorna
   HTTP 201 e o outro retorna HTTP 409, com uma única conta criada.

---

### User Story 3 - Registrar a criação para auditoria (Priority: P3)

A equipe responsável consegue verificar quando o cadastro foi criado e a autoria aplicável, sem
expor esses dados na resposta pública quando não fizerem parte do contrato.

**Why this priority**: A rastreabilidade é um princípio transversal do pi*VMA e o modelo atual já
prevê dados de auditoria.

**Independent Test**: Concluir um cadastro e verificar que os dados de criação previstos pelo
modelo foram registrados de acordo com a regra de autoria aprovada.

**Acceptance Scenarios**:

1. **Given** um cadastro válido, **When** a criação é concluída, **Then** o sistema registra a data
   e hora de criação.
2. **Given** um cadastro concluído sem sessão autenticada, **When** a auditoria é examinada,
   **Then** o campo de autoria permanece sem valor.
3. **Given** um cadastro público recém-concluído, **When** a auditoria é examinada, **Then**
   `updated_at`, `updated_by`, `deleted_at` e `deleted_by` permanecem nulos.

### Edge Cases

- Campos ausentes, vazios ou com formato de e-mail inválido devem ser rejeitados antes da criação.
- Usernames com menos de 3 ou mais de 64 caracteres, espaços ou caracteres fora de letras ASCII,
  números, ponto, hífen e sublinhado devem ser rejeitados.
- Uma falha durante a criação não pode deixar um usuário parcialmente cadastrado.
- Uma falha inesperada durante hashing, `flush` ou `commit` deve executar rollback e retornar HTTP
  500 genérico, sem expor detalhes internos, senha ou qualquer representação do segredo.
- Quando username e e-mail conflitam ao mesmo tempo, o sistema deve preservar a precedência
  observável já coberta pelo contrato atual: username antes de e-mail.
- Senhas com menos de 8 ou mais de 128 caracteres devem ser rejeitadas; senhas nos limites de 8 e
  128 caracteres devem ser aceitas sem exigência de classes específicas de caracteres.
- Senhas com qualquer caractere de espaço em branco devem ser rejeitadas; os demais caracteres
  Unicode devem ser aceitos e cada caractere deve contar uma unidade no limite de comprimento.
- O sistema deve remover espaços externos de username e e-mail antes de validá-los, compará-los,
  armazená-los e devolvê-los.
- As comparações de username e e-mail para verificar unicidade não devem distinguir maiúsculas de
  minúsculas.
- Após remover espaços externos, o sistema deve armazenar e exibir username e e-mail com a caixa
  fornecida pela pessoa.
- Em cada caso mínimo de concorrência, dois pedidos com username ou e-mail equivalentes devem
  produzir um HTTP 201, um HTTP 409 e uma única conta.
- Um usuário excluído logicamente libera seu username e seu e-mail para reuso por um novo cadastro,
  preservando o comportamento anterior a esta feature (ver Session 2026-08-12).
- A migração aborta sem alterar dados se encontrar colisão de `lower(username)` ou `lower(email)`
  entre usuários ativos, já que essa colisão violaria o novo índice único. A migração não inspeciona
  o formato da senha armazenada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE aceitar username, e-mail e senha como dados de um pedido de cadastro.
- **FR-002**: O backend DEVE validar a presença e o formato dos dados exigidos sem depender de
  controles de interface.
- **FR-003**: O sistema DEVE criar exatamente um usuário quando os dados forem válidos e os
  identificadores estiverem disponíveis.
- **FR-004**: O cadastro bem-sucedido DEVE retornar HTTP 201 com id, username e e-mail.
- **FR-005**: A resposta pública NÃO DEVE conter a senha, seu resumo seguro ou qualquer outra
  representação do segredo.
- **FR-006**: O sistema NÃO DEVE armazenar a senha em texto simples nem de forma reversível; deve
  armazenar somente uma representação segura adequada à verificação futura.
- **FR-007**: A senha aceita DEVE conter de 8 a 128 caracteres, inclusive, permitir caracteres
  Unicode e rejeitar qualquer caractere de espaço em branco, sem exigir maiúsculas, minúsculas,
  números, símbolos ou outras regras de composição; o sistema NÃO DEVE remover nem transformar
  caracteres antes de proteger a senha.
- **FR-008**: *(removido nesta versão, ver Session 2026-08-12)* Bloqueio de senhas comuns ou
  comprometidas por lista local versionada. Fora do escopo da v1; backlog futuro.
- **FR-009**: O username DEVE conter de 3 a 64 caracteres, inclusive, e aceitar somente letras
  ASCII, números, ponto, hífen e sublinhado, sem espaços.
- **FR-010**: O sistema DEVE impedir a criação quando o username já tiver sido utilizado e retornar
  HTTP 409 com a indicação de conflito de username.
- **FR-011**: O sistema DEVE impedir a criação quando o e-mail já tiver sido utilizado e retornar
  HTTP 409 com a indicação de conflito de e-mail.
- **FR-012**: O sistema DEVE remover espaços externos de username e e-mail antes de validar e
  comparar esses valores; ao armazená-los e retorná-los, DEVE preservar a caixa fornecida pela
  pessoa.
- **FR-013**: A comparação de e-mail para detectar duplicidade NÃO DEVE distinguir maiúsculas de
  minúsculas.
- **FR-014**: A comparação de username para detectar duplicidade NÃO DEVE distinguir maiúsculas de
  minúsculas; valores como `Brunna`, `brunna` e `BRUNNA` DEVEM representar o mesmo username
  para fins de unicidade.
- **FR-015**: Se username e e-mail conflitarem na mesma tentativa, o sistema DEVE informar primeiro
  o conflito de username, preservando o contrato atual.
- **FR-016**: Em cada caso mínimo com dois pedidos simultâneos usando username ou e-mail
  equivalentes, o sistema DEVE criar exatamente um usuário, retornar HTTP 201 para um pedido e HTTP
  409 para o outro.
- **FR-017**: Uma tentativa rejeitada NÃO DEVE criar nem modificar um usuário.
- **FR-018**: O sistema DEVE registrar a data e hora da criação por meio dos dados de auditoria já
  previstos.
- **FR-019**: Em um cadastro sem usuário autenticado, o sistema DEVE manter ausente a autoria da
  criação.
- **FR-020**: Alterações nos contratos existentes DEVEM ocorrer somente quando a segurança exigir
  mudança de comportamento documentada nesta especificação e coberta por testes.
- **FR-021**: A feature NÃO DEVE criar outros endpoints nem incluir login, JWT, cookies, perfis,
  permissões, vínculo institucional ou laboratorial, recuperação de senha ou mudanças em outros
  módulos.
- **FR-022**: A migração desta feature NÃO DEVE converter nem invalidar credenciais legadas; DEVE
  abortar sem alterar os dados se encontrar colisão de `lower(username)` ou `lower(email)` entre
  usuários ativos. A inspeção do formato da credencial armazenada foi removida nesta versão (ver
  Session 2026-08-12); o tratamento de credenciais legadas continua fora do escopo desta feature.
- **FR-023**: *(removido nesta versão, ver Session 2026-08-12)* Reserva de username e e-mail após
  exclusão lógica. A unicidade case-insensitive desta feature (FR-013, FR-014) passa a valer somente
  entre usuários ativos, como no comportamento anterior à feature.
- **FR-024**: *(removido nesta versão, ver Session 2026-08-12)* Prontidão fail-closed vinculada à
  blocklist. Depende de FR-008, também removido.
- **FR-025**: Esta feature NÃO DEVE implementar rate limiting; a política de limitação do cadastro
  público exige trabalho futuro separado com critérios próprios.
- **FR-026**: Se hashing, `flush` ou `commit` falhar de forma inesperada, o backend DEVE executar
  rollback, retornar HTTP 500 com mensagem genérica e NÃO DEVE criar ou modificar usuário nem
  expor detalhe interno, senha ou qualquer representação do segredo.
- **FR-027**: Imediatamente após o cadastro público, `updated_at`, `updated_by`, `deleted_at` e
  `deleted_by` DEVEM permanecer nulos.

### Key Entities

- **Usuário**: Conta cadastrada, identificada por id, username e e-mail; possui uma representação
  segura da senha e dados de criação para auditoria.
- **Dados de auditoria de criação**: Momento da criação e autoria aplicável vinculados ao usuário
  criado.
- **Lista de senhas bloqueadas**: Conjunto local e versionado de senhas comuns ou comprometidas
  que o cadastro deve rejeitar.

### Scope and Traceability

- **CONFIRMADO, fonte oficial**: RF001 prevê cadastro e autenticação de usuários. Esta feature cobre
  somente o cadastro.
- **CONFIRMADO, fonte oficial**: RF004 prevê controle de acesso conforme perfil, instituição e
  participação. Esta feature aplica validação no backend, mas deixa perfis, permissões e vínculos
  fora do escopo.
- **CONFIRMADO, implementação atual**: O cadastro já retorna id, username e e-mail; conflitos de
  username e e-mail retornam HTTP 409; os testes existentes registram esses contratos.
- **CONFIRMADO, implementação atual**: O modelo prevê data, hora e autoria de criação, mas o fluxo
  atual persiste a senha recebida sem proteção e não atribui autoria.
- **PROPOSTA desta feature**: Proteger a senha armazenada e completar a auditoria da criação sem
  ampliar o escopo para autenticação ou autorização por perfil.

### Matriz de rastreabilidade da implementação

**CONFIRMADO na implementação e nos testes de 2026-08-12**: cada requisito funcional possui a
seguinte prova automatizada ou inspeção de escopo. Os resultados de execução ficam registrados em
[quickstart.md](quickstart.md).

| Requisito | Cenário ou critério | Evidência principal |
|---|---|---|
| FR-001 | US1.1; SC-001 | `tests/routers/test_user.py`, `tests/test_schemas.py` |
| FR-002 | US1.4–1.6; SC-007–SC-010 | `tests/test_schemas.py`, `tests/routers/test_user.py` |
| FR-003 | US1.1; SC-001 | `tests/routers/test_user.py` |
| FR-004 | US1.1; SC-001 | `tests/routers/test_user.py` |
| FR-005 | US1.2; SC-002 | `tests/routers/test_user.py`, `tests/routers/test_user_failures.py` |
| FR-006 | US1.3; SC-003 | `tests/core/test_security.py`, `tests/routers/test_user.py` |
| FR-007 | US1.5; SC-007 | `tests/test_schemas.py`, `tests/core/test_security.py` |
| FR-008 | *(removido, ver Session 2026-08-12)* | — |
| FR-009 | US1.4; SC-009 | `tests/test_schemas.py` |
| FR-010 | US2.1; SC-004, SC-006 | `tests/routers/test_user.py`, `tests/core/database/test_user_constraints.py` |
| FR-011 | US2.2; SC-004, SC-006 | `tests/routers/test_user.py`, `tests/core/database/test_user_constraints.py` |
| FR-012 | Edge Case de trim e caixa; SC-008 | `tests/test_schemas.py`, `tests/routers/test_user.py` |
| FR-013 | US2.4; SC-004, SC-008 | `tests/routers/test_user.py`, `tests/routers/test_user_concurrency.py` |
| FR-014 | US2.5; SC-004, SC-008 | `tests/routers/test_user.py`, `tests/routers/test_user_concurrency.py` |
| FR-015 | US2.3; SC-006 | `tests/routers/test_user.py` |
| FR-016 | US2.6; SC-004 | `tests/routers/test_user_concurrency.py` |
| FR-017 | US1.4–1.5 e US2.1–2.6; SC-006, SC-013 | testes de rota e falhas |
| FR-018 | US3.1; SC-005 | `tests/routers/test_user_audit.py` |
| FR-019 | US3.2; SC-005 | `tests/routers/test_user_audit.py` |
| FR-020 | SC-006 | suíte completa e contrato `contracts/users.openapi.yaml` |
| FR-021 | Limites de escopo; SC-006 | inspeção do diff e da tabela de rotas existente |
| FR-022 | Edge Case de migração; SC-006 | `tests/migrations/test_secure_user_registration.py` |
| FR-023 | *(removido, ver Session 2026-08-12)* | — |
| FR-024 | *(removido, ver Session 2026-08-12)* | — |
| FR-025 | Limite de escopo | inspeção do diff: nenhum rate limiting adicionado |
| FR-026 | Edge Case de falha interna; SC-013 | `tests/routers/test_user_failures.py` |
| FR-027 | US3.3; SC-005 | `tests/routers/test_user_audit.py` |

**Cobertura adicional pós-redução de escopo (2026-08-12)**: `tests/core/database/test_user_constraints.py::test_deleted_user_identifiers_do_not_block_reuse` e `tests/routers/test_user.py::test_create_user_frees_identifiers_after_deletion` provam o comportamento revertido de FR-023 (identificador liberado após exclusão lógica).

## Success Criteria *(mandatory)*

### Measurable Outcomes

Para SC-001 a SC-010, o conjunto de validação é composto por todos os cenários de aceitação e edge
cases desta especificação, com ao menos um caso automatizado para cada cenário, limite e regra
enumerados. Os critérios SC-011 a SC-013 definem validações adicionais próprias.

- **SC-001**: Cada cadastro válido com identificadores disponíveis no conjunto de validação cria uma
  única conta e retorna id, username e e-mail.
- **SC-002**: Cada resposta de cadastro do conjunto de validação, bem-sucedida ou rejeitada, omite a
  senha e qualquer representação dela.
- **SC-003**: Cada usuário criado no conjunto de validação armazena somente uma representação não
  recuperável por leitura direta da senha original.
- **SC-004**: Para cada caso automatizado com dois pedidos simultâneos usando username ou e-mail
  equivalentes, inclusive com variações de caixa, um pedido retorna HTTP 201, o outro retorna HTTP
  409 e a contagem de usuários aumenta em uma unidade.
- **SC-005**: Cada cadastro concluído no conjunto de validação registra o momento da criação, mantém
  a autoria ausente quando não existe usuário autenticado e preserva `updated_at`, `updated_by`,
  `deleted_at` e `deleted_by` nulos imediatamente após a criação.
- **SC-006**: Todos os cenários automatizados de cadastro válido, proteção da senha, duplicidade,
  resposta pública e auditoria passam sem regressão nos contratos preservados.
- **SC-007**: No conjunto de validação, senhas fora do intervalo de 8 a 128 caracteres ou com
  whitespace são rejeitadas; senhas nos dois limites e com outros caracteres Unicode são aceitas
  quando os demais dados são válidos.
- **SC-008**: No conjunto de validação, o trim remove espaços externos e impede usernames e e-mails
  duplicados por variação de caixa.
- **SC-009**: No conjunto de validação, usernames fora do intervalo de 3 a 64 caracteres ou com
  caracteres não permitidos são rejeitados, e usernames válidos nos dois limites são aceitos quando
  os demais dados também são válidos.
- **SC-010**: *(removido nesta versão, ver Session 2026-08-12)* Dependia da blocklist local (FR-008).
- **SC-011**: *(removido nesta versão, ver Session 2026-08-12)* Deixou de ser gate de aceite formal;
  pode ser revisitado se houver indício de latência excessiva em uso real.
- **SC-012**: *(removido nesta versão, ver Session 2026-08-12)* Dependia da blocklist local (FR-008).
- **SC-013**: Os testes separados de falha no hashing, `flush` e `commit` confirmam HTTP 500
  genérico, rollback, ausência de criação parcial e ausência de detalhes internos ou segredos na
  resposta.

## Assumptions

- A feature atende ao cadastro previsto no RF001; autenticação permanece fora do escopo.
- O pedido de cadastro é público e não dispõe de identidade autenticada; por isso, a data e hora
  são registradas e a autoria permanece ausente.
- Os textos atuais de conflito, `Username already exists` e `Email already exists`, permanecem
  como contrato enquanto nenhuma necessidade de segurança exigir sua alteração.
- O identificador público do usuário continua sendo gerado pelo sistema.
- A comparação case-insensitive define somente a unicidade; username e e-mail preservam a caixa
  fornecida após a remoção de espaços externos.
- A reativação de contas excluídas logicamente não faz parte desta feature; username e e-mail
  ficam disponíveis para reuso por um novo cadastro assim que a conta original é excluída
  logicamente (ver Session 2026-08-12).
- A escolha do mecanismo de proteção da senha pertence ao plano técnico e deve demonstrar sua
  adequação sem introduzir autenticação, JWT ou cookies.
- Bloqueio de senhas comuns/comprometidas por lista local não faz parte desta versão; é um item de
  backlog explícito (ver Session 2026-08-12), não uma omissão silenciosa.
- A feature depende do fluxo existente de persistência de usuários e dos dados de auditoria já
  definidos no modelo.
- O tratamento de credenciais legadas continua fora do escopo desta feature. Como o projeto é novo
  e sem usuários reais em produção, a migração não inspeciona o formato da credencial armazenada
  (ver Session 2026-08-12); ela ainda aborta por colisão de identificador entre usuários ativos.
- Rate limiting do cadastro público permanece fora do escopo e requer feature futura separada.

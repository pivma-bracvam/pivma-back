# Feature Specification: Migração das listagens para o padrão e referências resumidas

**Feature Branch**: `feat/033-listing-migration-refs`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Spec 033: migrar as demais listagens da API para o padrão de listagem da Spec 032 (envelope data/pagination/filters_applied/sort, paginação por página) e trocar identificadores soltos e campos achatados de entidades relacionadas por referências resumidas (XRef), conforme alinhado em 2026-09-27."

## Contexto

A Spec 032 definiu o padrão de listagem da API e o aplicou à lista de tarefas. O envelope tem `data`, `pagination` por página, `filters_applied` e `sort`, e `facets` e `summary` sob demanda. As entidades relacionadas passam a vir como referências resumidas. As outras listagens continuam com o formato antigo. Esta spec migra 19 delas:

- 12 devolvem uma lista simples, sem paginação;
- 5 usam envelope por deslocamento (`items`, `offset`, `limit`);
- 1 usa envelope por página, mas com outros nomes (`items`, `page`, `size`, `total`);
- 1 é a linha do tempo do processo, que devolve os eventos dentro do recurso (`{process_id, code, events}`) e cresce sem limite.

As duas consultas de logs administrativos ficam fora: esses logs devem deixar de existir, e por ora só saem da documentação da API.

As entidades relacionadas também aparecem de três jeitos: identificador solto (participantes, convites, laboratórios), campos achatados (etiquetas de amostra, template do processo) e resumos embutidos com nomes próprios (afiliações).

Esta spec aplica o mesmo padrão a todas essas listagens e troca os identificadores soltos e os campos achatados por referências resumidas. A Spec 034 padroniza os erros. O frontend recebe as três specs juntas, num único changelog. O frontend usa deploy direto da `develop`, e a quebra temporária foi aceita.

Um ponto motiva a troca de identificadores: a tela de gestão de participantes e de vínculos de laboratório, pendente no frontend, hoje só recebe `user_id` e `laboratory_id`. Sem outras chamadas, ela não consegue mostrar nomes.

## Clarifications

### Session 2026-09-27

Decisões da conversa de alinhamento (valem para as Specs 032–034):

- Q: Todas as listagens adotam o envelope, inclusive as pequenas? → A: Sim, pela uniformidade: o frontend usa um componente de listagem só.
- Q: Paginação por página ou por deslocamento? → A: Por página.
- Q: Bloco de metadados (`meta`)? → A: Não por enquanto.
- Q: Como representar entidades relacionadas? → A: Referências resumidas de formato fixo por tipo, em um nível só, com descrição em cada campo. Campos de auditoria continuam como identificadores.
- Q: Specs separadas? → A: Sim, entregues ao frontend de uma vez.
- Q: A linha do tempo do processo e a lista de substâncias da atividade de amostras entram no padrão? → A: A linha do tempo entra; a lista de substâncias fica como está (coleção pequena, que carrega o status da atividade e acabou de entrar com a Spec 031).
- Q: Os logs administrativos (operacional e de IA) migram? → A: Não. Esses logs devem deixar de existir. Por ora, as duas consultas saem da documentação da API, sem mudar o comportamento, e não entram no changelog do frontend.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Toda listagem no mesmo formato (Priority: P1)

O frontend lista usuários, perfis, instituições, laboratórios, processos, participantes, convites, avaliações de IA e as demais coleções com o mesmo componente. Toda listagem responde no envelope padrão, pagina por página e informa os filtros e a ordenação aplicados.

**Why this priority**: É o objetivo da padronização. Enquanto uma listagem ficar fora do padrão, o frontend mantém código específico para ela.

**Independent Test**: Cada uma das 19 listagens, chamada sem parâmetros, responde com `data`, `pagination`, `filters_applied` e `sort`, e a paginação segue as mesmas regras de `GET /tasks`.

**Acceptance Scenarios**:

1. **Given** qualquer listagem da API, **When** o frontend a chama sem parâmetros, **Then** a resposta tem os blocos de itens, paginação, filtros aplicados e ordenação, com página 1 e 20 itens por página.
2. **Given** uma listagem com 25 itens, **When** o frontend pede a página 2 com 20 por página, **Then** recebe 5 itens, total de 25, 2 páginas e página anterior disponível.
3. **Given** uma listagem que hoje pagina por deslocamento, **When** o frontend usa página e tamanho de página, **Then** a paginação funciona, e os parâmetros antigos de deslocamento não são mais aceitos.
4. **Given** a listagem de processos, que hoje usa `size`, **When** o frontend usa o tamanho de página padrão, **Then** a paginação funciona com o mesmo nome das outras listagens.
5. **Given** uma listagem com filtros existentes (ex.: busca de usuários, status de processos), **When** o frontend filtra, **Then** o filtro funciona como antes e aparece nos filtros aplicados.
6. **Given** uma listagem sem filtros, **When** a resposta chega, **Then** os filtros aplicados vêm vazios.
7. **Given** qualquer listagem, **When** o frontend chama duas vezes com os mesmos dados, **Then** a ordem é a mesma, e a ordenação aplicada aparece na resposta.

---

### User Story 2 - Participantes e vínculos com nomes (Priority: P1)

Quem gere o processo abre a tela de participantes e vê, para cada designação, o nome da pessoa, o cargo e, nos cargos de laboratório, o laboratório e a instituição, sem outras chamadas. Nos convites, vê o laboratório do convite.

**Why this priority**: Destrava a tela de gestão de participantes e de vínculos de laboratório, pendente no frontend.

**Independent Test**: A lista de participantes de um processo com um laboratório participante traz a pessoa como referência (identificador, usuário e nome completo) e o laboratório como referência com a instituição embutida.

**Acceptance Scenarios**:

1. **Given** um processo com um laboratório participante designado, **When** o gestor lista os participantes, **Then** cada item traz a pessoa (identificador, usuário e nome completo) e o laboratório (identificador, nome, situação e instituição).
2. **Given** um participante sem laboratório (ex.: Grupo Gestor), **When** ele aparece na lista, **Then** o laboratório vem nulo.
3. **Given** um convite para um cargo de laboratório, **When** o gestor lista os convites, **Then** o convite traz o laboratório como referência.
4. **Given** o histórico de participantes, **When** o gestor o consulta, **Then** cada designação do histórico usa as mesmas referências.
5. **Given** quem só pode ver a própria designação, **When** lista os participantes, **Then** continua vendo só a própria. As referências não ampliam o que cada perfil vê.
6. **Given** qualquer referência a pessoa, **When** aparece numa resposta, **Then** não traz e-mail.

---

### User Story 3 - Referências no catálogo, nos processos e nas etiquetas (Priority: P2)

O frontend mostra a instituição de cada laboratório, a instituição e o laboratório das afiliações, o template e a versão de cada processo e o laboratório de cada etiqueta de amostra a partir das referências, sem montar nomes a partir de campos soltos.

**Why this priority**: Completa a convenção no resto da API. Essas telas já funcionam com os campos atuais, mas ficariam fora do padrão.

**Independent Test**: Um laboratório traz `institution` como referência; uma afiliação traz `user`, `institution` e `laboratory` como referências; um processo traz `template` com chave, nome e versão; uma etiqueta traz `laboratory` como referência.

**Acceptance Scenarios**:

1. **Given** um laboratório, **When** aparece na listagem ou no detalhe, **Then** traz a instituição como referência no lugar do identificador solto.
2. **Given** uma afiliação, **When** aparece na listagem, **Then** traz a pessoa, a instituição e o laboratório como referências.
3. **Given** um processo, **When** aparece na listagem ou no detalhe, **Then** traz o template como referência (chave, nome e versão) no lugar da chave e da versão soltas.
4. **Given** uma etiqueta de amostra, **When** o Grupo de Seleção lista as etiquetas, **Then** traz o laboratório como referência no lugar do identificador e do nome soltos, sem nada que identifique a substância além do que já vem hoje.
5. **Given** um usuário na listagem administrativa, **When** aparece com seus perfis, **Then** os perfis vêm como referências.

---

### User Story 4 - Referências documentadas (Priority: P3)

Quem consome a API encontra, na documentação interativa, um schema por tipo de referência, com descrição em todos os campos, e cada listagem com o envelope tipado.

**Why this priority**: O changelog manda o frontend conferir os formatos na documentação.

**Independent Test**: A documentação não mostra as consultas de logs administrativos e lista as referências de pessoa, perfil, instituição, laboratório e template, todas com descrição em todos os campos, e descreve cada listagem como envelope.

**Acceptance Scenarios**:

1. **Given** a documentação da API, **When** alguém consulta qualquer uma das 19 listagens, **Then** a resposta é descrita como envelope com os itens tipados.
2. **Given** a documentação da API, **When** alguém consulta os schemas de referência, **Then** todo campo tem descrição.
3. **Given** a documentação da API, **When** alguém procura as consultas de logs administrativos, **Then** elas não aparecem.

---

### Edge Cases

- Listagem de catálogo pequeno (permissões, perfis, templates, referências de IA, afiliações próprias): também pagina, com os mesmos limites. O frontend pede `per_page=100` quando quiser tudo de uma vez.
- Mais de 100 etiquetas num processo (ex.: 10 substâncias × 12 laboratórios): a impressão exige percorrer as páginas.
- Página além da última: lista vazia com os totais corretos, como em `GET /tasks`.
- Laboratório ou instituição desativados: a referência continua aparecendo, com a indicação de situação.
- Pessoa desativada ainda referenciada numa designação antiga: a referência continua aparecendo com o nome.
- Parâmetros antigos (`offset`, `limit`, `size`) enviados por um cliente desatualizado: são ignorados, e a resposta usa a página padrão. Os filtros aplicados mostram o que valeu.
- Linha do tempo com muitos eventos: pagina como as demais listagens, na ordem cronológica atual. O código e o título do processo deixam de vir na resposta; o frontend já os tem na tela do processo.
- Consultas de logs administrativos: continuam respondendo como hoje para quem chamar diretamente, mas não aparecem na documentação da API.

## Requirements *(mandatory)*

### Functional Requirements

**Listagens**

- **FR-001**: As 19 listagens abaixo DEVEM responder no envelope padrão da Spec 032 (itens, paginação por página, filtros aplicados, ordenação):
  - usuários (administração);
  - permissões, perfis e alterações do RBAC;
  - instituições, laboratórios, afiliações de um usuário, afiliações próprias e alterações do catálogo institucional;
  - templates de processo, processos e versões de submissão;
  - linha do tempo do processo;
  - participantes, histórico de participantes e convites;
  - avaliações de IA e referências de IA;
  - etiquetas de amostra.
- **FR-002**: A paginação DEVE seguir as regras da Spec 032: página a partir de 1, tamanho padrão 20, máximo 100, valor fora dos limites recusado com erro de validação, e página além da última com lista vazia e totais corretos.
- **FR-003**: Os parâmetros de paginação antigos (`offset`, `limit`, `size`) DEVEM deixar de existir nas listagens migradas.
- **FR-004**: Os filtros existentes em cada listagem DEVEM continuar funcionando com o mesmo significado e aparecer nos filtros aplicados, inclusive os valores padrão. Listagens sem filtros DEVEM devolver filtros aplicados vazios.
- **FR-005**: Cada listagem DEVE manter a ordenação que tem hoje como padrão, com desempate determinístico, e informá-la na ordenação aplicada. Esta spec não adiciona ordenação configurável.
- **FR-006**: A migração NÃO DEVE mudar quem vê o quê: as mesmas permissões, escopos e isolamentos de hoje valem para os itens e para os totais.

**Referências resumidas**

- **FR-007**: Os tipos de referência DEVEM ter formato fixo:
  - pessoa: identificador, nome de usuário e nome completo, nunca e-mail;
  - perfil: identificador, nome e situação;
  - instituição: identificador, nome e situação;
  - laboratório: identificador, nome, situação e a instituição como referência;
  - template de processo: chave, nome e versão.

  A referência de processo e a de etapa da Spec 032 continuam como estão.
- **FR-008**: As designações de participantes (lista, histórico, respostas de designação) DEVEM trazer o processo, a pessoa e o laboratório (ou nulo) como referências, no lugar de `process_id`, `user_id` e `laboratory_id`.
- **FR-009**: Os convites DEVEM trazer o processo e o laboratório (ou nulo) como referências, no lugar de `process_id` e `laboratory_id`.
- **FR-010**: Os laboratórios DEVEM trazer a instituição como referência, no lugar de `institution_id`.
- **FR-011**: As afiliações DEVEM trazer a pessoa (quando a resposta hoje traz `user_id`), a instituição e o laboratório como referências, no lugar dos resumos atuais.
- **FR-012**: Os processos (listagem e detalhe) DEVEM trazer o template como referência, no lugar de `template_key` e `version_number`.
- **FR-013**: As etiquetas de amostra DEVEM trazer o laboratório como referência, no lugar de `laboratory_id` e `laboratory_name`.
- **FR-014**: Os perfis de um usuário na listagem administrativa DEVEM vir como referências de perfil.
- **FR-015**: Campos de auditoria (quem criou, alterou, excluiu, aceitou, revogou, designou ou executou) e alvos polimórficos das trilhas de alteração DEVEM continuar como identificadores.
- **FR-016**: A troca por referências vale para o schema, então alcança também as respostas de detalhe, criação e alteração que usam o mesmo schema das listagens.
- **FR-017**: Toda referência e todo envelope DEVEM ter descrição em todos os campos na documentação da API.

**Fora do padrão**

- **FR-018**: As consultas de logs administrativos (operacional e de IA) NÃO DEVEM aparecer na documentação da API. O comportamento e o acesso delas não mudam nesta spec, e elas não entram no changelog do frontend.
- **FR-019**: A lista de substâncias da atividade de amostras NÃO muda nesta spec.

### Key Entities

- **Envelope de listagem**: o mesmo da Spec 032.
- **Referência de pessoa**: identificador, nome de usuário, nome completo.
- **Referência de perfil**: identificador, nome, situação.
- **Referência de instituição**: identificador, nome, situação.
- **Referência de laboratório**: identificador, nome, situação, instituição.
- **Referência de template**: chave, nome, versão.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das listagens documentadas da API (as 19 desta spec mais a de tarefas) respondem no mesmo envelope e aceitam os mesmos parâmetros de paginação.
- **SC-002**: A tela de participantes mostra nome da pessoa, cargo, laboratório e instituição de cada designação com uma única chamada.
- **SC-003**: Nenhuma resposta traz e-mail dentro de uma referência de pessoa.
- **SC-004**: Para cada perfil de acesso, o número de itens e os totais de cada listagem são os mesmos antes e depois da migração.
- **SC-005**: Nenhuma resposta de listagem passa de 100 itens.
- **SC-006**: Pedidos repetidos com os mesmos parâmetros e os mesmos dados devolvem a mesma ordem em 100% das vezes, em todas as listagens.

## Assumptions

- As listagens com filtros hoje mantêm exatamente esses filtros, sem novos.
- A referência de pessoa traz nome de usuário e nome completo. O e-mail fica de fora, porque as referências aparecem para perfis que não gerem usuários.
- Instituição e laboratório trazem a situação (ativo/inativo), porque as telas de catálogo e de afiliações já mostram isso com os resumos atuais.
- As respostas que não são listagens, mas contêm coleções próprias de um recurso (campos de formulário, versões de uma avaliação, critérios, anexos), continuam como estão.
- Os campos `created_by`, `updated_by`, `deleted_by`, `assigned_by`, `accepted_by`, `revoked_by`, `actor_user_id` e o `user_id` dos eventos da linha do tempo são de auditoria e continuam como identificadores.
- Os alvos das trilhas de alteração (RBAC e catálogo) são polimórficos (tipo + identificador) e continuam assim.
- A linha do tempo não tem filtros hoje; os filtros aplicados vêm vazios. A ordem padrão continua cronológica crescente.
- Remover de fato os logs administrativos (rotas, serviço, arquivos) fica para uma spec própria.
- O formato das respostas de erro continua o atual; a Spec 034 o padroniza.
- A mudança quebra os contratos de todas as listagens citadas e dos schemas com referências novas. Vai para o changelog único das Specs 032–034.

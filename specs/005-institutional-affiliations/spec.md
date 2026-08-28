# Feature Specification: Vinculação Institucional

**Feature Branch**: `develop`

**Created**: 2026-08-24

**Status**: Ready for Planning

**Input**: User description: "Criar a especificação da feature 005 para implementar RF003: Vinculação institucional, cobrindo instituições, laboratórios, vínculos de usuários, cardinalidade, estados, autorização, auditoria, isolamento, migração, schemas, endpoints e testes, sem implementar RF005, RF006, refresh token, 2FA ou mensageria e sem inventar regras ausentes."

## Clarifications

### Session 2026-08-24

- Q: Como instituições, laboratórios e múltiplos vínculos de usuário devem se relacionar? → A: Cada laboratório pertence a uma instituição. O usuário pode ter vários vínculos ativos, cada um com uma instituição e, opcionalmente, um laboratório dela. Todos os vínculos ativos formam seu escopo, sem vínculo principal.
- Q: Como o backend deve separar a consulta e a administração dos dados institucionais? → A: O sistema usa `institutional.read` para consulta global e histórico, `institutional.catalogs.manage` para gerir instituições e laboratórios e `institutional.affiliations.manage` para gerir vínculos. O perfil Administrador recebe as três permissões. Usuários autenticados consultam os próprios vínculos ativos sem permissão adicional.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manter instituições e laboratórios (Priority: P1)

Uma pessoa com a capacidade de gestão dos catálogos institucionais mantém o cadastro mínimo de instituições e laboratórios que
identificam a origem institucional dos usuários da plataforma.

**Why this priority**: Os vínculos de RF003 dependem de instituições e laboratórios identificados
por registros estáveis e ativos.

**Independent Test**: Criar uma instituição e um laboratório, consultar os registros, alterar seus
nomes e inativá-los, conferindo o estado e os dados de auditoria após cada operação.

**Acceptance Scenarios**:

1. **Given** uma pessoa autenticada com gestão dos catálogos institucionais e dados válidos, **When** ela cadastra uma instituição ou laboratório, **Then** o sistema cria um registro ativo com identificador estável, responsável e momento da criação.
2. **Given** um registro ativo, **When** uma pessoa autorizada altera seu nome, **Then** o sistema mantém o identificador e registra o responsável e o momento da alteração.
3. **Given** um registro ativo, **When** uma pessoa autorizada o inativa, **Then** o sistema encerra seu uso em novas vinculações e preserva o registro para consulta histórica.
4. **Given** uma pessoa sem a capacidade exigida, **When** ela tenta criar, alterar ou inativar um registro, **Then** o backend nega a operação sem modificar dados.
5. **Given** uma pessoa que pode gerir vínculos, mas não catálogos, **When** ela tenta criar, alterar ou inativar uma instituição ou laboratório, **Then** o backend nega a operação sem modificar dados.

---

### User Story 2 - Vincular usuários (Priority: P1)

Uma pessoa com a capacidade de gestão de vínculos institucionais vincula uma conta ativa às instituições e aos laboratórios
nos quais ela atua. O sistema usa somente vínculos ativos para formar o escopo institucional da
conta.

**Why this priority**: O vínculo entre usuário, instituição e laboratório constitui o resultado
central do RF003 e fornece contexto para o controle de acesso previsto no RF004.

**Independent Test**: Criar um vínculo para uma conta ativa, consultar seu escopo, inativar o
vínculo e confirmar que ele deixa de conceder contexto no pedido seguinte, sem perder o histórico.

**Acceptance Scenarios**:

1. **Given** uma conta ativa e registros institucionais ativos, **When** uma pessoa autorizada cria um vínculo válido, **Then** o vínculo passa a compor o escopo institucional da conta.
2. **Given** um vínculo ativo, **When** uma pessoa autorizada o inativa, **Then** ele deixa de compor o escopo da conta no pedido seguinte e continua disponível no histórico.
3. **Given** uma conta, instituição ou laboratório inativo, **When** alguém tenta criar um vínculo, **Then** o sistema rejeita a operação sem criar registro parcial.
4. **Given** um vínculo ativo equivalente, **When** duas solicitações concorrentes tentam criá-lo, **Then** o sistema mantém um único vínculo ativo e rejeita a duplicação.
5. **Given** um vínculo ativo associado ao escopo incorreto, **When** uma pessoa autorizada corrige a vinculação, **Then** o sistema encerra o ciclo incorreto e cria outro vínculo sem substituir o histórico.
6. **Given** uma pessoa que pode gerir catálogos, mas não vínculos, **When** ela tenta criar ou inativar um vínculo, **Then** o backend nega a operação sem modificar dados.

---

### User Story 3 - Consultar somente o escopo autorizado (Priority: P2)

Uma pessoa autenticada consulta os próprios vínculos ativos. A capacidade de leitura institucional
permite consultar os catálogos, os vínculos de outras contas e o histórico.

**Why this priority**: O Plano de Trabalho exige acesso individualizado e isolamento entre
laboratórios. RF003 deve fornecer um contexto confiável sem substituir as regras futuras de
participação em processo.

**Independent Test**: Preparar duas contas vinculadas a laboratórios distintos e confirmar que uma
conta sem capacidade global não consulta vínculos nem dados protegidos do outro laboratório.

**Acceptance Scenarios**:

1. **Given** duas contas com escopos institucionais distintos e sem capacidade de leitura global, **When** uma delas tenta consultar os vínculos da outra, **Then** o backend nega o acesso sem revelar o conteúdo protegido.
2. **Given** uma conta cujo vínculo foi inativado durante uma sessão válida, **When** ela faz o pedido seguinte, **Then** o backend usa o estado atual e não considera o vínculo encerrado.
3. **Given** uma pessoa com capacidade de leitura institucional, **When** ela consulta vínculos, **Then** o sistema permite a consulta global e retorna somente os campos autorizados.
4. **Given** um cliente que envia nomes de perfil, instituição ou laboratório, **When** o backend avalia o acesso, **Then** ele usa a identidade, as permissões e os vínculos persistidos, sem confiar nos indicadores enviados pelo cliente.

---

### User Story 4 - Consultar o histórico de vínculos (Priority: P3)

Uma pessoa com a capacidade de leitura institucional identifica quem criou, alterou ou inativou instituições,
laboratórios e vínculos, além do momento de cada mudança concluída.

**Why this priority**: RF034 exige registro de usuários, datas e alterações. O histórico permite
explicar por que uma conta possuía determinado escopo em um momento anterior.

**Independent Test**: Executar uma criação, uma alteração e uma inativação com uma conta
autorizada e consultar os registros históricos correspondentes.

**Acceptance Scenarios**:

1. **Given** uma mudança institucional concluída, **When** uma pessoa autorizada consulta o histórico, **Then** o sistema informa a ação, o alvo, o responsável e o momento da mudança.
2. **Given** um vínculo inativado e outro criado depois para a mesma combinação aprovada, **When** a pessoa consulta o histórico, **Then** o sistema apresenta os dois ciclos sem substituir o primeiro.
3. **Given** uma tentativa negada ou inválida, **When** ela termina sem alteração, **Then** o sistema não cria um evento de mudança concluída.

### Edge Cases

- Duas pessoas tentam cadastrar ao mesmo tempo registros que violam a regra de unicidade ativa definida para o catálogo. O sistema mantém um único registro válido e não deixa alterações parciais.
- Uma pessoa tenta vincular uma conta excluída logicamente. O sistema rejeita a operação.
- Uma instituição ou laboratório é inativado enquanto existem vínculos ativos. O sistema preserva esses vínculos no histórico e deixa de considerá-los no escopo efetivo.
- Uma conta possui vínculos em mais de uma instituição ou laboratório. O backend considera a união dos vínculos ativos, sem exigir vínculo principal ou contexto selecionado.
- Uma pessoa altera no pedido o identificador de usuário, instituição ou laboratório para sondar outro escopo. O backend mantém a negação e não expõe dados protegidos.
- Uma pessoa tenta usar um vínculo institucional para assumir responsabilidade em um processo. O sistema não cria designação, pois RF005 está fora desta feature.
- Uma migração é aplicada a uma instalação com usuários e RBAC existentes. Ela preserva as contas, os perfis, as atribuições e os contratos atuais sem criar vínculos institucionais implícitos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE exigir identidade autenticada para criar, alterar, inativar ou consultar dados institucionais protegidos.
- **FR-002**: O sistema DEVE manter instituições com identificador estável, nome, estado ativo ou inativo e dados de auditoria.
- **FR-003**: O sistema DEVE manter laboratórios com identificador estável, nome, estado ativo ou inativo e dados de auditoria.
- **FR-004**: Cada laboratório DEVE pertencer a exatamente uma instituição, e uma instituição PODE possuir nenhum, um ou vários laboratórios.
- **FR-005**: Nomes e identificadores apresentados ao usuário NÃO DEVEM atuar como prova de autorização; o backend DEVE usar os registros persistidos.
- **FR-006**: O sistema DEVE tratar o vínculo institucional como dado de autorização separado do cadastro da conta e da atribuição de perfil global.
- **FR-007**: Uma conta PODE possuir vários vínculos ativos. Cada vínculo DEVE identificar uma instituição e PODE identificar um laboratório ativo pertencente a essa instituição. O sistema DEVE considerar a união dos vínculos ativos sem exigir vínculo principal ou seleção de contexto.
- **FR-008**: O sistema DEVE criar vínculos somente entre contas ativas e instituições ou laboratórios ativos.
- **FR-009**: O sistema DEVE impedir vínculos ativos duplicados para a mesma combinação aprovada de conta, instituição e laboratório, inclusive em solicitações concorrentes.
- **FR-010**: A inativação de um vínculo DEVE produzir efeito nos pedidos posteriores da conta sem exigir nova autenticação.
- **FR-011**: A inativação de uma instituição ou laboratório DEVE retirar seu efeito do escopo institucional das contas vinculadas, sem apagar os vínculos históricos.
- **FR-012**: Uma correção ou nova vinculação após o encerramento de um vínculo DEVE iniciar outro ciclo rastreável, sem alterar, reativar nem sobrescrever o ciclo anterior.
- **FR-013**: Esta feature DEVE usar somente os estados ativo e inativo para instituições, laboratórios e vínculos. Ela NÃO DEVE excluir fisicamente registros nem introduzir fluxos de aprovação.
- **FR-014**: O sistema DEVE usar `institutional.read` para consulta global de instituições, laboratórios, vínculos e histórico, `institutional.catalogs.manage` para criar, alterar e inativar instituições e laboratórios e `institutional.affiliations.manage` para criar e inativar vínculos. O perfil Administrador DEVE receber as três permissões na carga inicial, e os outros perfis NÃO DEVEM recebê-las nesta feature.
- **FR-015**: Uma conta autenticada sem permissão institucional DEVE consultar somente os próprios vínculos ativos. As três permissões institucionais possuem alcance global, são independentes e não dependem de vínculo institucional do responsável.
- **FR-016**: O sistema NÃO DEVE conceder acesso a dados de outra instituição ou laboratório somente porque a conta possui o mesmo perfil global de uma pessoa vinculada a esse outro escopo.
- **FR-017**: Uma resposta negada NÃO DEVE retornar o conteúdo protegido nem confirmar a existência de registro fora do escopo da pessoa.
- **FR-018**: Esta feature DEVE aplicar isolamento aos catálogos, vínculos e histórico que ela administra e fornecer o escopo institucional ativo para autorização futura. Ela NÃO DEVE definir acesso por participação, fase ou responsabilidade dentro de um processo.
- **FR-019**: O sistema DEVE associar cada criação, alteração e inativação concluída ao responsável autenticado e ao momento da operação, conforme o padrão de auditoria existente.
- **FR-020**: O sistema DEVE registrar no histórico de mudanças institucionais a ação concluída, o tipo e o identificador do alvo, o responsável e o momento.
- **FR-021**: O sistema DEVE permitir que uma pessoa com `institutional.read` consulte vínculos ativos e inativos e ordene o histórico de modo determinístico.
- **FR-022**: Registros inativos DEVEM permanecer disponíveis apenas para consultas históricas autorizadas e NÃO DEVEM aceitar novas vinculações nem conceder escopo.
- **FR-023**: O sistema DEVE preservar os contratos de cadastro, autenticação e RBAC definidos pelas features 001, 002 e 003. Alterações institucionais DEVEM produzir efeito pelo estado persistido no pedido seguinte.
- **FR-024**: A migração desta feature DEVE criar as estruturas persistentes de instituições, laboratórios, vínculos e histórico de mudanças, com auditoria, integridade referencial e unicidade ativa compatível com FR-004 e FR-007.
- **FR-025**: A migração NÃO DEVE criar vínculos implícitos para contas existentes nem alterar perfis e atribuições atuais. Ela DEVE registrar `institutional.read`, `institutional.catalogs.manage` e `institutional.affiliations.manage` no catálogo e conceder as três ao perfil protegido de Administrador.
- **FR-026**: Os schemas de entrada DEVEM aceitar apenas os campos necessários para criar ou alterar instituições, laboratórios e vínculos. Os schemas de saída DEVEM expor identificadores, estado e auditoria autorizada sem devolver dados de outro escopo.
- **FR-027**: A interface HTTP DEVE oferecer operações para listar e consultar instituições e laboratórios, criar e alterar registros, inativá-los, listar e criar vínculos de usuário, inativar vínculos e consultar o histórico autorizado.
- **FR-028**: Operações que alteram estado DEVEM aplicar a proteção de origem já exigida para autenticação por cookie.
- **FR-029**: Os testes DEVEM cobrir validação de schemas, contratos HTTP, separação entre as três permissões institucionais, isolamento entre escopos, auditoria, inativação, concorrência, constraints de persistência, aplicação e reversão da migração e regressão das features 001 a 003.
- **FR-030**: Esta feature NÃO DEVE implementar designações por processo, conflito de interesse, refresh token, 2FA, mensageria, seleção de laboratórios para ensaio, cegamento ou regras de revelação de identidades.

### Key Entities

- **Instituição**: Unidade institucional que pode integrar o escopo de uma conta e possuir vários laboratórios. Mantém identificador, nome, estado e auditoria.
- **Laboratório**: Unidade laboratorial participante que pertence a uma instituição. Mantém identificador, nome, estado e auditoria.
- **Vínculo institucional do usuário**: Relaciona uma conta ativa a uma instituição e, quando aplicável, a um laboratório dessa instituição. Uma conta pode acumular vínculos ativos, e cada ciclo preserva início, encerramento, autoria e datas.
- **Mudança institucional**: Registra uma criação, alteração ou inativação concluída sobre instituição, laboratório ou vínculo.
- **Conta de usuário**: Identidade cadastrada e autenticável definida pelas features 001 e 002.
- **Permissão institucional**: Capacidade global do RBAC. `institutional.read` autoriza consulta global e histórica, `institutional.catalogs.manage` autoriza mutações em instituições e laboratórios e `institutional.affiliations.manage` autoriza mutações em vínculos. O perfil Administrador recebe as três na carga inicial.

## Required Technical Coverage for Planning

Esta seção delimita os artefatos que o plano deve detalhar. Ela não define nomes de arquivos,
classes ou rotas antes das decisões de `clarify`.

| Área | Cobertura necessária |
|---|---|
| Migração | Criar estruturas para instituição, laboratório, vínculo e histórico; aplicar auditoria, referências e unicidade ativa; cadastrar as permissões aprovadas; preservar dados existentes; permitir reversão. |
| Schemas | Separar entradas de criação e alteração das saídas públicas; rejeitar campos extras; representar estado, auditoria e histórico conforme a autorização. |
| Endpoints de catálogo | Listar, consultar, criar, alterar e inativar instituições e laboratórios. |
| Endpoints de vínculo | Listar vínculos ativos e históricos de uma conta, criar vínculo e inativar vínculo. |
| Endpoint de histórico | Consultar mudanças institucionais com paginação e ordenação determinística. |
| Testes | Cobrir unidade de schemas, API, segurança e isolamento, persistência e concorrência, migração e regressão. |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários automatizados, somente pessoas com a capacidade e o escopo aprovados concluem uma criação, alteração, inativação ou consulta protegida.
- **SC-002**: Em 100% dos cenários de isolamento, uma conta sem alcance global não recebe vínculos nem dados protegidos de outra instituição ou laboratório.
- **SC-003**: Em 100% dos cenários de inativação, o registro deixa de conceder escopo no pedido seguinte e permanece disponível no histórico autorizado.
- **SC-004**: Em 100% das mudanças institucionais concluídas, uma pessoa autorizada identifica a ação, o alvo, o responsável e o momento correspondente.
- **SC-005**: O conjunto de validação cobre conta sem vínculo, conta com múltiplos vínculos ativos, vínculo apenas institucional, vínculo laboratorial, registros inativos, duplicação e solicitações concorrentes.
- **SC-006**: Durante validação manual cronometrada, uma pessoa autorizada cadastra uma instituição e um laboratório e vincula uma conta em até 3 minutos.
- **SC-007**: Todos os cenários existentes das features 001, 002 e 003 continuam válidos após a introdução dos vínculos institucionais.
- **SC-008**: Após a disponibilização da feature, 100% das contas preservam seus perfis e atribuições preexistentes e nenhuma recebe vínculo institucional implícito.
- **SC-009**: Em 100% dos cenários de separação administrativa, possuir uma das três permissões institucionais não concede as outras duas.

## Assumptions

- **CONFIRMADO, fonte oficial**: RF003 exige a vinculação dos usuários às instituições e aos laboratórios participantes, conforme `docs/plano-de-trabalho-fase-ii.md`, seção 3.1.
- **CONFIRMADO, fonte oficial**: RF004 condiciona o acesso ao perfil, à instituição e à participação no processo. RF034 exige logs e auditoria. RF044 exige que cada laboratório veja somente seus dados durante etapas restritas do ensaio.
- **DECISÃO TÉCNICA REGISTRADA**: O backend trata vínculos institucionais como dados de autorização, separados de campos de perfil, conforme `docs/planejamento/gestao-de-usuarios.md`.
- **DECISÃO TÉCNICA REGISTRADA**: O backend aplica RBAC e autorização contextual; controles de interface não substituem essa validação.
- **CONFIRMADO, constituição 1.0.0**: A implementação deve preservar o padrão de auditoria atual e impedir exposição entre laboratórios quando o domínio exigir isolamento.
- **CONFIRMADO, implementação atual em `develop`**: O sistema possui contas com exclusão lógica, autenticação por cookie, RBAC global com consulta no pedido atual e auditoria por criação, atualização e exclusão lógica. O código não possui instituição, laboratório ou vínculo institucional.
- **DECISÃO da Session 2026-08-24**: Cada laboratório pertence a uma instituição. Uma conta pode manter múltiplos vínculos ativos, cada um com uma instituição e, de forma opcional, um laboratório dessa instituição. Todos os vínculos ativos formam o escopo da conta, sem vínculo principal.
- **DECISÃO da Session 2026-08-24**: O sistema separa consulta global, gestão de catálogos e gestão de vínculos nas permissões `institutional.read`, `institutional.catalogs.manage` e `institutional.affiliations.manage`. O perfil Administrador recebe as três. Qualquer conta autenticada consulta os próprios vínculos ativos sem permissão adicional.
- **ASSUMPTION delimitadora**: Esta feature usa ativo e inativo como ciclo mínimo, preserva registros encerrados e cria novo ciclo quando uma vinculação equivalente volta a existir. A etapa `clarify` pode revisar esse padrão se a equipe exigir reativação ou outros estados.
- **ASSUMPTION delimitadora**: Nome constitui o único dado descritivo obrigatório de instituição e laboratório nesta feature. CNPJ, endereço, acreditação, contatos e metadados regulatórios dependem de requisito posterior.
- **ASSUMPTION delimitadora**: O histórico institucional desta feature registra mudanças concluídas. Retenção, retificação e consulta da trilha geral de auditoria permanecem para especificação posterior.

## Scope and Traceability

| Fonte | Natureza | Cobertura nesta feature |
|---|---|---|
| RF003 | Requisito oficial | Cobertura integral do cadastro mínimo de instituições e laboratórios e da vinculação institucional de usuários. |
| RF004 | Requisito oficial relacionado | Cobertura do contexto institucional para autorização dos dados desta feature; participação em processo fica para RF005. |
| RF034 | Requisito oficial transversal | Auditoria e histórico das mudanças institucionais concluídas. |
| RF044 | Requisito oficial transversal | Isolamento verificável dos dados institucionais e laboratoriais desta feature; regras por etapa do ensaio ficam fora do escopo. |
| Backlog de Gestão de Usuários | Decisão técnica registrada | Vínculos como dados de autorização, validação no backend e preservação do histórico. |
| Features 001 a 003 | Especificações e implementação existentes | Reutiliza conta, autenticação, RBAC, proteção de origem, auditoria e exclusão lógica sem alterar seus contratos. |
| Observações e pendências | Controle de lacunas | As decisões desta feature resolvem a multiplicidade de vínculos e separam as três capacidades institucionais; regras contextuais de processo permanecem pendentes para as features correspondentes. |

## Out of Scope

- Designação de participantes por processo prevista no RF005.
- Declaração ou efeito de conflito de interesse previsto no RF006.
- Seleção de laboratórios para um ensaio, atribuições locais, responsabilidades por fase ou participação em processo.
- Cegamento, códigos cegos, revelação de identidades e matriz de acesso por etapa do ensaio.
- Cadastro público de instituições ou laboratórios e aprovação de pedidos de vínculo.
- Administração geral de contas, alterações no RBAC além das permissões institucionais aprovadas e permissões de outros módulos.
- Administração delegada limitada a uma instituição ou laboratório; esta feature usa apenas permissões institucionais globais e autoconsulta.
- Refresh token, rotação ou revogação de sessão, 2FA, recuperação de conta, confirmação de e-mail e mensageria.
- Endereço, CNPJ, acreditação, contatos e outros cadastros administrativos de instituições e laboratórios sem requisito aprovado.

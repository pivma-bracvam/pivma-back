# Feature Specification: Simplificação de Cargos Globais (RBAC)

**Feature Branch**: `023-rbac-global-roles`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Simplificação de cargos globais (RBAC): reduzir os perfis globais (AccessProfile) do sistema para apenas três — Padrão (nenhum perfil global atribuído), Administrador e BraCVAM — e garantir que Administrador e BraCVAM tenham todas as permissões do sistema ativas, para simplificar o desenvolvimento e a autorização. Os demais perfis globais hoje semeados nas migrations (Grupo Gestor, Gerente do Estudo, Laboratório Participante, Avaliador Ad Hoc, Revisor, Especialista, Analista Estatístico, e um perfil global 'proponent') não têm nenhuma permissão vinculada hoje e devem ser descontinuados como perfis globais. Não afeta os papéis locais por processo (Assignment.role_key / ActivityCargo da Feature 018). É uma dependência externa registrada pela Spec 022, que exige que triage.review continue sendo outorgada somente a Admin/BraCVAM."

## Contexto e classificação

- **CONFIRMADO** (migration `c1e4a9f8b312_user_authorization_rbac.py`): existem hoje 9 perfis globais (`AccessProfile`) originais — `proponent`, `management_group` ("Grupo Gestor"), `study_manager` ("Gerente do Estudo"), `participating_laboratory` ("Laboratório Participante"), `ad_hoc_evaluator` ("Avaliador Ad Hoc"), `reviewer` ("Revisor"), `specialist` ("Especialista"), `statistical_analyst` ("Analista Estatístico") e `administrator` ("Administrador") — mais `bracvam` ("BraCVAM"), adicionado pela migration `d3f9a1c47b28_bracvam_profile_triage_permission.py`.
- **CONFIRMADO** (mesmas migrations): somente `administrator` e `bracvam` têm alguma `Permission` vinculada hoje. `administrator` tem `rbac.read`, `rbac.profiles.manage`, `rbac.assignments.manage` e `triage.review`; `bracvam` tem `triage.review`, `ai_evaluations.read` e `ai_evaluations.manage`. Os outros 7 perfis (`management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`) e o perfil global `proponent` não têm nenhuma `Permission` vinculada.
- **CONFIRMADO** (`src/pivma/core/authorization.py`): `has_platform_wide_access` já trata apenas `administrator`/`bracvam` como perfil global de plataforma (`PLATFORM_WIDE_SYSTEM_KEYS`); os outros 7 perfis não participam dessa checagem em nenhum ponto do código.
- **CONFIRMADO**: existe exatamente uma checagem de autorização, em todo o código de produção, que reconhece um perfil global pelo nome fora do sistema de `Permission`: `can_manage_process_templates` checa `p.name in {'Administrador', 'Grupo Gestor'}`.
- **CONFIRMADO**: os identificadores `study_manager`, `participating_laboratory` e `ad_hoc_evaluator` também existem como **papel local por processo** (`Assignment.role_key` / `ActivityCargo`, Feature 018) — uma tabela e um mecanismo de autorização totalmente independentes de `AccessProfile`, que usam os mesmos nomes por coincidência de vocabulário de domínio, não por serem a mesma entidade.
- **CONFIRMADO por decisão do responsável da demanda**: os únicos perfis globais que devem existir daqui em diante são "Padrão" (nenhum `AccessProfile` atribuído — o estado de qualquer usuário sem promoção), "Administrador" e "BraCVAM"; Administrador e BraCVAM devem ter todas as permissões do sistema ativas, para que o time não precise lembrar de conceder cada permissão nova a eles manualmente.
- **DECISÃO TÉCNICA REGISTRADA**: esta spec é a dependência externa que a Spec 022 (revisão de exclusão/arquivamento de processos, 2026-09-13) registrou — ela assume que `triage.review` é outorgada somente a Admin/BraCVAM. Essa condição **já é verdadeira hoje** (nenhum outro perfil concede `triage.review`); esta spec formaliza essa garantia como parte permanente da matriz de cargos, em vez de uma coincidência do estado atual dos dados.
- **PROPOSTA**: o mecanismo técnico exato para "Admin/BraCVAM têm toda permissão, inclusive as futuras, sem migration adicional" é uma decisão de design (checagem de código vs. composição de dados) a resolver no `/speckit-plan`, não nesta especificação.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrador e BraCVAM operam sem barreira de permissão (Priority: P1)

Como Administrador ou como integrante do BraCVAM, quero ter todas as permissões do sistema ativas no meu perfil, para não esbarrar em barreiras de autorização ao operar qualquer funcionalidade da plataforma, presente ou futura.

**Why this priority**: é o núcleo do pedido. Hoje Admin/BraCVAM só têm as permissões explicitamente concedidas a eles; uma permissão nova criada por uma feature futura não é automaticamente concedida, forçando uma migration extra toda vez que alguém esquece.

**Independent Test**: autenticar como Administrador e como BraCVAM e confirmar, via consulta ao efetivo de permissões de cada um, que toda `Permission` cadastrada no sistema está presente.

**Acceptance Scenarios**:

1. **Given** qualquer `Permission` cadastrada no sistema, **When** o efetivo de permissões de um usuário com perfil Administrador é consultado, **Then** essa permissão está presente.
2. **Given** qualquer `Permission` cadastrada no sistema, **When** o efetivo de permissões de um usuário com perfil BraCVAM é consultado, **Then** essa permissão está presente.
3. **Given** uma nova `Permission` criada por uma feature futura, **When** ela é inserida no catálogo de permissões, **Then** Administrador e BraCVAM já a possuem, sem exigir uma migration de composição adicional.

---

### User Story 2 - Perfis globais sem função são descontinuados (Priority: P1)

Como responsável técnico do RBAC, quero que os 7 perfis globais hoje sem nenhuma permissão vinculada, mais o perfil global `proponent`, deixem de existir como perfis atribuíveis, para que a lista de perfis globais reflita exatamente o que o sistema usa hoje.

**Why this priority**: reduz a superfície de RBAC ao que tem efeito real e remove a confusão entre "perfil global" e "papel local por processo" que esses nomes coincidentes causam para quem lê o código ou administra contas.

**Independent Test**: consultar a listagem de perfis atribuíveis e confirmar que somente Administrador e BraCVAM aparecem; tentar atribuir um dos perfis descontinuados retorna um erro previsível.

**Acceptance Scenarios**:

1. **Given** os 7 perfis sem permissão hoje mais o perfil global `proponent`, **When** esta feature é aplicada, **Then** eles deixam de existir como `AccessProfile` ativos (soft-deletados, preservando histórico de auditoria).
2. **Given** um usuário que hoje tem um desses perfis atribuído, **When** esta feature é aplicada, **Then** essa atribuição é revogada e o usuário passa a ter o estado "Padrão" (nenhum `AccessProfile` ativo), sem perder nenhum papel local por processo.
3. **Given** a listagem de perfis atribuíveis após esta feature, **When** qualquer usuário autorizado consulta, **Then** somente Administrador e BraCVAM aparecem.
4. **Given** um perfil descontinuado, **When** alguém tenta atribuí-lo a um usuário, **Then** a operação é rejeitada de forma previsível.

---

### User Story 3 - "Padrão" é o estado sem perfil global (Priority: P2)

Como qualquer usuário sem perfil global atribuído, quero que meu estado seja tratado uniformemente como "Padrão", para que a ausência de perfil não seja um caso especial não documentado em nenhuma parte do sistema.

**Why this priority**: hoje a ausência de vínculo de perfil já significa, na prática, "sem poder algum"; esta história formaliza esse estado como o terceiro cargo canônico, mas não muda comportamento observável por si só — por isso tem prioridade menor que unificar as histórias 1 e 2.

**Independent Test**: um usuário recém-registrado, sem nenhum perfil atribuído, é identificado como "Padrão" em qualquer lugar da API que hoje exponha o(s) perfil(is) de um usuário.

**Acceptance Scenarios**:

1. **Given** um usuário sem `UserAccessProfile` ativo algum, **When** seu perfil é consultado, **Then** o sistema o identifica de forma estável como "Padrão" (ausência de perfil), sem exigir um `AccessProfile` literal para representar esse estado.

### Edge Cases

- O único Administrador restante do sistema tem seu perfil revogado nesta migração ou por engano depois — a regra já existente de "ao menos um Administrador ativo" (Feature 003) continua se aplicando e barra a operação.
- Uma `Permission` nova é criada por uma migration futura e ninguém lembra de concedê-la manualmente a Admin/BraCVAM — o mecanismo de concessão automática desta feature (FR-001/FR-002) evita essa lacuna recorrente.
- Um perfil descontinuado é referenciado por uma entrada histórica de auditoria (`RbacChange`) anterior a esta feature — o histórico não é apagado nem reescrito; apenas o perfil deixa de aceitar novas atribuições.
- Um papel local por processo (`Assignment.role_key`) tem o mesmo nome de um perfil global descontinuado (ex.: `study_manager`) — a revogação do perfil global não afeta, revoga ou reinterpreta nenhuma `Assignment` existente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE conceder a Administrador e a BraCVAM toda `Permission` ativa cadastrada no sistema.
- **FR-002**: Toda nova `Permission` criada a partir desta feature em diante DEVE estar automaticamente coberta pelo FR-001, sem exigir uma migration de composição adicional específica para Admin/BraCVAM.
- **FR-003**: Os perfis globais `management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst` e `proponent` DEVEM ser descontinuados como `AccessProfile` atribuíveis.
- **FR-004**: A descontinuação DEVE preservar o histórico: os perfis são soft-deletados, nunca removidos fisicamente, e qualquer `RbacChange` anterior permanece consultável e inalterado.
- **FR-005**: Qualquer `UserAccessProfile` ativo vinculado a um dos perfis descontinuados DEVE ser revogado (soft-deletado) como parte desta feature.
- **FR-006**: A revogação do FR-005 NÃO DEVE afetar papéis locais por processo (`Assignment`/`ActivityCargo`, Feature 018), que são um mecanismo independente de `AccessProfile`, mesmo quando o nome coincide.
- **FR-007**: Após esta feature, a listagem de perfis atribuíveis DEVE mostrar somente Administrador e BraCVAM.
- **FR-008**: A regra existente de "ao menos um Administrador ativo" (Feature 003) DEVE continuar valendo sem alteração de comportamento.
- **FR-009**: Um usuário sem nenhum `UserAccessProfile` ativo DEVE ser identificável de forma estável como "Padrão", sem exigir um `AccessProfile` literal para esse estado.
- **FR-010**: Esta feature NÃO DEVE alterar `Assignment.role_key`, `ActivityCargo` ou qualquer papel local por processo, mesmo quando o nome coincide com um perfil global descontinuado.
- **FR-011**: A verificação de gestão de templates de processo, que hoje reconhece o perfil global "Grupo Gestor" pelo nome, DEVE deixar de depender desse perfil (já que ele é descontinuado) e passar a se basear apenas em perfil Administrador/BraCVAM ou em uma permissão explícita do catálogo.
- **FR-012**: Esta feature NÃO DEVE alterar o comportamento observável da Spec 022 além de formalizar sua pré-condição externa — a concessão de `triage.review` restrita a Admin/BraCVAM, já verdadeira hoje na prática.
- **FR-013**: Esta feature NÃO DEVE criar papel local novo, tabela nova, ou redesenhar o motor de autorização por processo (Feature 018); o escopo é estritamente os perfis globais (`AccessProfile`).

### Key Entities *(include if feature involves data)*

- **AccessProfile**: perfil global de RBAC. Após esta feature, restrito a `administrator` e `bracvam` como ativos; os demais perfis hoje existentes são soft-deletados.
- **Permission**: catálogo de permissões atômicas. Administrador e BraCVAM passam a estar cobertos por todas as permissões ativas, presentes e futuras.
- **UserAccessProfile**: vínculo usuário↔perfil global. Atribuições aos perfis descontinuados são revogadas; usuários afetados passam ao estado "Padrão".
- **"Padrão"**: não é uma linha de `AccessProfile` — é o estado observável de um usuário sem nenhum `UserAccessProfile` ativo.
- **Assignment / ActivityCargo** (Feature 018, não alterada por esta feature): papel local por processo, mecanismo independente de `AccessProfile`, mencionado aqui apenas para deixar explícito o que esta feature **não** toca.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das consultas ao efetivo de permissões, Administrador e BraCVAM têm todas as permissões cadastradas no sistema no momento da consulta.
- **SC-002**: Em 100% das consultas à listagem de perfis atribuíveis, apenas Administrador e BraCVAM aparecem.
- **SC-003**: Em 100% dos usuários que tinham um perfil descontinuado antes desta feature, nenhum papel local por processo é perdido ou alterado.
- **SC-004**: Em 100% do histórico de RBAC anterior a esta feature (`RbacChange`, atribuições passadas), a consulta permanece possível e os dados permanecem inalterados.
- **SC-005**: A suíte de testes da Spec 022 continua passando sem nenhuma alteração de código relacionada a processos, confirmando que a pré-condição externa já estava satisfeita.

## Assumptions

- **INFERÊNCIA**: como nenhum dos 7 perfis descontinuados (além de `proponent` global) tem `Permission` vinculada hoje, sua descontinuação não retira nenhuma capacidade de nenhum usuário atualmente — apenas fecha a possibilidade de atribuí-los daqui em diante e formaliza o que, na prática, já eram perfis sem efeito.
- O mecanismo técnico exato de "toda `Permission`, inclusive futuras, sem migration por permissão nova" (checagem de código que trata `administrator`/`bracvam` como universais, vs. um gatilho de banco que replica composições automaticamente) é uma decisão a resolver no `/speckit-plan`, não nesta especificação.
- Esta feature não introduz nenhum perfil, papel local, tabela ou coluna nova; opera inteiramente sobre o esquema de RBAC já existente (Feature 003), sobre a permissão `triage.review` (Feature 014) e sobre a distinção de perfis de plataforma (Feature 018).
- Nenhum usuário de produção depende hoje de um dos 7 perfis descontinuados para alguma capacidade real, dado que eles não carregam `Permission` — a revogação de `UserAccessProfile` (FR-005) é, na prática, uma limpeza de dados sem efeito funcional observável para esses usuários.

## Dependencies and Traceability

- **Feature 003 (Autorização RBAC)**: define `AccessProfile`, `Permission`, `UserAccessProfile`, `RbacChange` e a regra `ensure_administrator_remains`, todos reutilizados sem alteração estrutural por esta feature.
- **Feature 014 (Semântica BraCVAM e autorização da triagem)**: cria o perfil `bracvam` e a permissão `triage.review`, concedida hoje somente a `administrator`/`bracvam` — condição que esta feature formaliza como permanente.
- **Feature 018 (Kanban, atividades e cargos)**: define `PLATFORM_WIDE_SYSTEM_KEYS` (`administrator`/`bracvam`) e os papéis locais por processo (`Assignment.role_key`/`ActivityCargo`) que usam nomes parecidos aos perfis globais descontinuados, mas são um mecanismo independente e não são alterados por esta feature.
- **Feature 022 (Exclusão e arquivamento de processos, revisão 2026-09-13)**: dependente externa desta spec — sua autorização de arquivamento (`triage.review`) e de exclusão (perfil global Admin/BraCVAM) assume a matriz de cargos que esta feature formaliza. Nenhuma mudança de código da 022 é esperada como consequência desta feature, já que a condição já é verdadeira hoje.

# Feature Specification: Fechar Escalada de Privilégio em Templates e Endpoints Administrativos (Issue #39)

**Feature Branch**: `027-template-authz-escalation`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "https://github.com/pivma-bracvam/pivma-back/issues/39 — brecha de escalada de privilégio em can_manage_process_templates e require_admin"

## Contexto

Duas funções de autorização do backend (`can_manage_process_templates` em
`core/authorization.py` e `require_admin` em `dependencies.py`) tratam a
permissão `rbac.read` — documentada no próprio catálogo canônico como
"Consultar o estado do RBAC", ou seja, só leitura — como se fosse prova de
privilégio administrativo. Qualquer perfil de acesso customizado que receba
essa permissão (concedida por quem tiver `rbac.profiles.manage`, que pode
estar delegado a alguém que não é administrador) passa a poder:

- Editar a definição de templates de processo/formulário (`PUT
  /processes/templates/{key}/forms/{form_key}`), uma estrutura declarativa
  crítica hoje controlada como código (versionada em YAML, sincronizada por
  script de bootstrap).
- Acessar endpoints hoje reservados a administradores: reprocessar pipelines
  de avaliação por IA e consultar streams de log operacionais/de IA.

Adicionalmente, `can_manage_process_templates` também concede a mesma
capacidade de editar templates para qualquer perfil cujo **nome de exibição**
(campo de texto livre, não o identificador canônico do sistema) seja
literalmente `"Administrador"` — mesmo que esse perfil não tenha o
`system_key` oficial de administrador.

Esta spec cobre o fechamento das duas brechas nas duas funções citadas pela
issue. Ao investigar a correção, identificou-se que travar
`can_manage_process_templates` estritamente em `system_key ==
'administrator'` — como a issue original propõe — quebraria uma regra de
negócio real: a equipe BraCVAM precisa poder editar a definição de
formulários (adicionar/ajustar campos) como parte do seu trabalho
operacional. Hoje isso não tem nenhum caminho legítimo — o perfil `bracvam`
canônico só tem `triage.review`, `ai_evaluations.read` e
`ai_evaluations.manage` (confirmado na migration
`d3f9a1c47b28_bracvam_profile_triage_permission.py`); na prática, essa
necessidade só é satisfeita hoje através da própria brecha de segurança
(`rbac.read` ou um perfil nomeado "Administrador"). Configurar avaliação por
IA já é tratado corretamente por `ai_evaluations.manage`, em um endpoint
separado — não faz parte da brecha.

Por isso, esta spec introduz uma permissão nova e discreta,
`form_templates.manage`, no mesmo padrão já usado para as outras capacidades
do BraCVAM (`triage.review`, `ai_evaluations.*`), em vez de reaproveitar um
critério bruto por `system_key`. `can_manage_process_templates` passa a
aceitar administrador **ou** essa permissão nova; `require_admin` (que
guarda reprocessamento de IA e streams de log — nada disso solicitado pelo
BraCVAM) continua estrito a `system_key == 'administrator'`, sem a permissão
nova.

## Clarifications

### Session 2026-09-17

- Q: Travar a edição de template estritamente em `system_key ==
  'administrator'`, como o texto original da issue propõe, é aceitável? → A:
  Não — a equipe BraCVAM precisa editar formulários (adicionar campos) como
  parte do seu trabalho, e hoje só consegue isso através da própria brecha.
  A correção não pode fechar a brecha derrubando essa capacidade real.
- Q: Como conceder esse acesso ao BraCVAM de forma correta — reaproveitando
  `system_key in {administrator, bracvam}` (mesmo padrão de
  `has_platform_wide_access`) ou por uma permissão discreta nova? → A:
  Permissão discreta nova (`form_templates.manage`), concedida ao perfil
  `bracvam` no seed canônico — mesmo padrão já usado para
  `triage.review`/`ai_evaluations.*`, evitando reintroduzir um critério
  bruto por `system_key` como proxy de autorização.
- Q: A correção precisa de um passo de auditoria/migração para identificar
  contas reais que hoje dependem da brecha antes do deploy? → A: Não — o
  ambiente é recriado do zero (banco derrubado e subido de novo, populado
  pelo bootstrap) neste estágio do projeto; a permissão nova já nasce
  concedida ao perfil `bracvam` desde a primeira subida, sem conta órfã para
  migrar manualmente.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Impedir edição de template por quem não tem autorização de fato, sem quebrar o uso legítimo do BraCVAM (Priority: P1)

Uma pessoa com um perfil de acesso customizado que inclui a permissão
`rbac.read` (concedida, por exemplo, para consultar quem tem qual permissão
no sistema) tenta editar a definição de um template de processo ou
formulário. Hoje essa tentativa é aceita; deveria ser recusada, porque
`rbac.read` é uma permissão de consulta, não de administração. Ao mesmo
tempo, uma pessoa da equipe BraCVAM, com a nova permissão
`form_templates.manage` concedida ao seu perfil, precisa continuar
conseguindo editar formulários — essa é uma necessidade real de negócio, não
uma brecha.

**Why this priority**: É a brecha de maior impacto — permite alterar em
tempo de execução uma estrutura que o projeto trata como imutável em runtime
("Templates as Code"), abrindo caminho para *config drift* e quebra da
máquina de estados de fases subsequentes do processo. Corrigi-la sem
preservar a necessidade real do BraCVAM criaria uma regressão funcional no
mesmo golpe.

**Independent Test**: Criar um usuário com um perfil customizado que só
tenha a permissão `rbac.read` associada e confirmar que uma chamada `PUT
/processes/templates/{key}/forms/{form_key}` retorna 403. Repetir com um
perfil customizado nomeado literalmente "Administrador", mas sem o
`system_key` oficial, e confirmar o mesmo resultado. Confirmar que uma conta
com o perfil oficial de Administrador continua conseguindo editar
normalmente. Confirmar, por fim, que uma conta com um perfil que tenha
`form_templates.manage` (como o perfil `bracvam` passa a ter) também
consegue editar normalmente.

**Acceptance Scenarios**:

1. **Given** um usuário cujo único perfil ativo concede a permissão
   `rbac.read` e nada mais, **When** ele chama `PUT
   /processes/templates/{key}/forms/{form_key}`, **Then** a API responde 403
   e a definição do template não é alterada.
2. **Given** um usuário cujo único perfil ativo tem `name = "Administrador"`
   mas `system_key` diferente de `'administrator'`, **When** ele chama o
   mesmo endpoint, **Then** a API responde 403.
3. **Given** um usuário com o perfil oficial de Administrador (`system_key
   == 'administrator'`), **When** ele chama o mesmo endpoint, **Then** a
   edição é aceita normalmente, sem nenhuma mudança de comportamento.
4. **Given** um usuário com um perfil ativo que concede a permissão
   `form_templates.manage` (o perfil `bracvam` canônico, depois desta
   correção), **When** ele chama o mesmo endpoint, **Then** a edição é
   aceita normalmente.

---

### User Story 2 - Impedir acesso administrativo por quem só tem permissão de leitura de RBAC (Priority: P1)

A mesma pessoa do cenário anterior, com um perfil que só concede
`rbac.read`, tenta reprocessar um pipeline de avaliação por IA ou abrir um
stream de logs operacionais/de IA — ações hoje reservadas a administradores.
Hoje essas tentativas são aceitas; deveriam ser recusadas pelo mesmo motivo:
`rbac.read` nunca deveria equivaler a "sou administrador".

**Why this priority**: Mesma severidade da User Story 1 — expõe operações
sensíveis (reprocessamento de IA, telemetria interna) a qualquer perfil que
tenha sido concedido acesso de leitura ao RBAC, sem relação nenhuma com a
intenção original dessa permissão.

**Independent Test**: Com o mesmo usuário só-`rbac.read` da User Story 1,
chamar um endpoint que dependa de `require_admin` (ex.: reprocessamento de
avaliação por IA) e confirmar 403. Confirmar que uma conta com o perfil
oficial de Administrador continua tendo acesso normal.

**Acceptance Scenarios**:

1. **Given** um usuário cujo único perfil ativo concede a permissão
   `rbac.read` e nada mais, **When** ele chama um endpoint que depende de
   `require_admin`, **Then** a API responde 403.
2. **Given** um usuário com o perfil oficial de Administrador, **When** ele
   chama o mesmo endpoint, **Then** o acesso é concedido normalmente.

---

### Edge Cases

- O que acontece com um usuário que tem **dois** perfis ativos, um deles
  oficial de Administrador e outro customizado com `rbac.read`? Continua
  autorizado — a checagem correta (`system_key == 'administrator'` em
  qualquer perfil ativo) já cobre esse caso hoje e não deve regredir.
- O que acontece com um perfil oficial de Administrador que foi
  soft-deletado (`deleted_at` preenchido)? Não deve mais conceder nenhum dos
  dois acessos — comportamento que já é a regra geral de perfis inativos no
  sistema e não deve mudar com esta correção.
- A permissão `rbac.read` continua servindo para seu propósito original
  (consultar o estado do RBAC via `GET /rbac/...`)? Sim — esta correção só
  remove `rbac.read` como atalho para privilégio administrativo nas duas
  funções citadas; o uso legítimo de leitura do RBAC não é afetado.
- O que acontece com um perfil `bracvam` customizado (não o canônico) que
  não tenha recebido `form_templates.manage` explicitamente? Continua
  recusado na edição de templates — a nova permissão precisa estar
  associada ao perfil, não é implícita por `system_key == 'bracvam'`.
  Reforça que o critério é a permissão discreta, não o cargo.
- `form_templates.manage` concede acesso a `require_admin` (reprocessamento
  de IA, streams de log)? Não — essas duas capacidades continuam estritas a
  `system_key == 'administrator'`; a nova permissão só afeta
  `can_manage_process_templates`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE recusar (HTTP 403) qualquer tentativa de editar
  a definição de um template de processo/formulário vinda de um usuário cujo
  único critério de acesso seja a permissão `rbac.read`, sem nenhum perfil
  ativo com `system_key == 'administrator'` nem com a permissão
  `form_templates.manage`.
- **FR-002**: O sistema DEVE recusar (HTTP 403) a mesma tentativa de edição
  quando o único critério de acesso for um perfil cujo nome de exibição seja
  `"Administrador"`, mas cujo `system_key` não seja `'administrator'` e que
  também não tenha `form_templates.manage`.
- **FR-003**: O sistema DEVE recusar (HTTP 403) o acesso a qualquer endpoint
  hoje protegido por `require_admin` (reprocessamento de avaliação por IA,
  streams de log administrativos) vindo de um usuário cujo único critério de
  acesso seja a permissão `rbac.read` ou `form_templates.manage` — esses
  endpoints permanecem estritos a `system_key == 'administrator'`.
- **FR-004**: O sistema DEVE continuar concedendo os dois acessos acima
  (edição de template e endpoints administrativos) a qualquer usuário com um
  perfil ativo cujo `system_key` seja `'administrator'`, sem nenhuma
  regressão de comportamento para esse caso.
- **FR-005**: A permissão `rbac.read` DEVE continuar funcionando para seu
  propósito original de leitura do estado do RBAC, sem nenhuma mudança nos
  endpoints que hoje a exigem legitimamente para esse fim.
- **FR-006**: O sistema DEVE ter cobertura de teste automatizado para: (a)
  usuário só com `rbac.read` sendo recusado nas duas funções de autorização
  corrigidas; (b) perfil nomeado "Administrador" sem o `system_key` oficial
  sendo recusado; (c) administrador oficial continuando autorizado nos dois
  casos; (d) usuário com `form_templates.manage` autorizado a editar
  template, mas recusado em endpoints de `require_admin`.
- **FR-007**: O sistema DEVE introduzir a permissão `form_templates.manage`
  no catálogo canônico e concedê-la ao perfil `bracvam` canônico, para que a
  equipe BraCVAM continue editando formulários por um caminho legítimo
  depois que os dois atalhos indevidos (FR-001, FR-002) forem fechados.

### Key Entities *(include if feature involves data)*

- **Permission**: catálogo canônico de permissões já existente; ganha um
  registro novo, `form_templates.manage`, descrevendo "gerir a definição de
  formulários de processo (campos, nome, descrição)".
- **AccessProfile**: perfil `bracvam` canônico já existente; ganha a
  associação com a nova permissão, ao lado das que já tem
  (`triage.review`, `ai_evaluations.read`, `ai_evaluations.manage`). O
  perfil `administrator` já recebe automaticamente toda permissão do
  catálogo (mapeamento existente), incluindo a nova, sem alteração adicional.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das tentativas de editar um template de processo ou
  formulário partindo de uma conta sem o perfil oficial de Administrador e
  sem a permissão `form_templates.manage` são recusadas com 403 — hoje,
  contas com `rbac.read` ou com um perfil chamado "Administrador" conseguem
  completar essa edição.
- **SC-002**: 100% das tentativas de acessar um endpoint administrativo
  (reprocessamento de IA, streams de log) partindo de uma conta sem o perfil
  oficial de Administrador são recusadas com 403 — inclusive contas que
  tenham `form_templates.manage` mas não sejam administradoras.
- **SC-003**: 100% das contas com o perfil oficial de Administrador, e 100%
  das contas com `form_templates.manage` (perfil `bracvam` canônico
  incluído), mantêm acesso à edição de templates sem nenhuma regressão
  observável — a equipe BraCVAM continua editando formulários normalmente
  depois da correção.
- **SC-004**: Nenhum endpoint, schema de request ou de resposta muda de
  forma — a correção fica inteiramente contida na camada de autorização e no
  catálogo de permissões (nova linha de dado, não novo contrato).

## Assumptions

- O endpoint `PUT /processes/templates/{key}/forms/{form_key}` permanece
  disponível (a issue oferece como alternativa "desativar ou blindar" o
  endpoint); a abordagem escolhida é blindar — restringir a `system_key ==
  'administrator'` **ou** à nova permissão `form_templates.manage` — em vez
  de remover a capacidade de edição de templates, que é uma necessidade de
  negócio real do BraCVAM, confirmada nesta sessão de clarificação.
- Uma permissão nova (`form_templates.manage`) é criada e concedida ao
  perfil `bracvam` canônico — decisão explícita desta sessão de
  clarificação, para não perpetuar a necessidade do BraCVAM através de um
  critério bruto por `system_key` nem através da brecha de segurança
  original. Nenhum perfil, endpoint ou tabela novos além dessa permissão.
- `endpoints` protegidos por `require_admin` (reprocessamento de IA, streams
  de log) **não** recebem a nova permissão como critério válido — continuam
  estritos a `system_key == 'administrator'`, porque nada indicou
  necessidade do BraCVAM sobre essas duas capacidades especificamente.
- `ADMINISTRATIVE_PERMISSIONS` (conjunto usado por
  `ensure_administrator_remains` para impedir que o sistema fique sem
  nenhum administrador pleno) não faz parte desta correção nem inclui
  `form_templates.manage` — é um mecanismo diferente, que já usa a
  combinação completa de permissões administrativas como critério, não
  `rbac.read` isoladamente, e não apresenta a mesma brecha.
- Nenhum passo de auditoria/migração de contas existentes é necessário —
  decisão desta sessão de clarificação, dado que o ambiente do projeto neste
  estágio é recriado do zero (banco derrubado e recriado, populado pelo
  bootstrap canônico) em vez de receber migração incremental de dados de
  usuários reais.

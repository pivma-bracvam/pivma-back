# Research: Definição e Preparação das Amostras — estudo cego

Decisões técnicas da Spec 031, levantadas a partir do código em `develop`
(commit `1b8de1a`). As decisões de produto estão em `spec.md`, seção
Clarifications.

## R1 — A atividade de amostras usa o motor genérico de atividades

- **Decision**: declarar a atividade `sample_definition` no YAML de cada
  template, com `activity_type: "sample_definition"`, `assigned_role:
  "sample_selection_group"`, `access.edit: ["sample_selection_group"]`,
  `access.view: []` e dependências `ACTIVITY_COMPLETED` em
  `assign_sample_selection_group` e `assign_participating_laboratory`.
- **Rationale**: `_advance_dependent_activities` já destrava qualquer
  atividade cujas dependências fecharam e cria execução e tarefa
  (`_activate_activity`). As atividades de atribuição de cargo fecham na
  primeira designação sem convite pendente (`_maybe_close_role_assignment_activity`).
  Nada no motor precisa mudar para abrir a atividade.
- **Alternatives considered**: endpoint próprio de amostras sem atividade
  (rejeitada pelo usuário: sem conclusão nem tarefa); atividade `form` com
  formulário dinâmico (não representa a relação substância × laboratório nem
  a geração de códigos).

## R2 — Fase 2 nos templates 01, 02, 03 e 05

- **Decision**: copiar para esses YAMLs o bloco `phase_2_role_assignment` do
  template 04 (oito atividades, mesmos responsáveis, acessos e dependências) e
  acrescentar `sample_definition` à Fase 2 dos cinco templates. Versões: 01,
  02, 03 e 05 passam de 2 para 3; 04 passa de 4 para 5.
- **Rationale**: `bootstrap_all_templates` cria uma `ProcessTemplateVersion`
  nova quando o `version` do YAML muda e preserva as anteriores; cada processo
  lê a versão gravada na instância (`template_version_id`). Isso cumpre FR-004
  sem migração de dados.
- **Alternatives considered**: extrair a Fase 2 para um arquivo comum incluído
  por todos (abstração nova no carregador de YAML, sem ganho que justifique;
  a cópia é explícita e o teste de estrutura detecta divergência).
- **Impacto em testes existentes**:
  `tests/api/routers/test_activity_type_extension.py::test_template_detail_defaults_activity_type_for_legacy_templates`
  supõe que os templates 01, 02, 03 e 05 só têm atividades `form` e
  `return_review`; precisa aceitar `role_assignment` e `sample_definition`.

## R3 — Acesso ao conteúdo de amostras = concessão de edição

- **Decision**: toda rota de conteúdo (substâncias, códigos, etiquetas, SDS,
  rota do frasco) chama `require_activity_access(..., 'edit')` sobre a
  atividade `sample_definition`, mesmo em leituras.
- **Rationale**: `resolve_activity_access` sempre põe `admin` e `bracvam` em
  `view_roles` (Spec 030), e isso deve continuar para que eles vejam a
  atividade e seu status (FR-023). O conteúdo, porém, só pode ir para
  `sample_selection_group`, que é exatamente `edit_roles`. Exigir edição dá:
  laboratório e Grupo Gestor → 404 (não veem a atividade); admin e BraCVAM →
  403 (veem, não editam); Grupo de Seleção → acesso. Nenhuma regra nova de
  autorização.
- **Consequência aceita**: um membro do Grupo com conflito de interesse
  vigente também perde a leitura, porque `require_activity_access` bloqueia
  edição por conflito. É o lado conservador para cegamento.
- **Alternatives considered**: nova função `require_activity_content_access`
  que exclui cargos globais (duplica a regra que `edit_roles` já expressa);
  remover `admin`/`bracvam` de `view_roles` desta atividade (quebra FR-023 e o
  invariante da Spec 030 de que eles veem toda atividade).

## R4 — Laboratórios que recebem códigos

- **Decision**: laboratórios distintos (`Assignment.laboratory_id`) das
  designações `participating_laboratory` com `revoked_at` e `deleted_at`
  nulos, cujo `Laboratory` não está excluído.
- **Rationale**: a Spec 006 exige `laboratory_id` para cargos de laboratório;
  vários usuários do mesmo laboratório geram um único código por substância
  (FR-012). `lead_laboratory` não entra (Assumptions).
- **Alternatives considered**: usar `compute_effectiveness_map` (também
  verifica afiliação ativa do usuário). Mais restritivo do que a spec pede; um
  laboratório continua participante mesmo que um de seus usuários perca a
  afiliação.

## R5 — Formato e geração do código cego

- **Decision**: 8 caracteres de `secrets.choice` sobre o alfabeto
  `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (31 símbolos, sem `0/O`, `1/I/L`).
  Unicidade garantida por índice único parcial `(process_instance_id, code)`
  e verificada antes da inserção; em colisão, gera outro (até 10 tentativas,
  depois erro 500 registrado).
- **Rationale**: `secrets` é criptograficamente seguro e não depende de
  ordem; 31⁸ ≈ 8,5 × 10¹¹ torna colisão improvável num processo com dezenas
  de códigos. Sem prefixo de substância ou laboratório (FR-011).
- **Alternatives considered**: hash de (substância, laboratório, segredo)
  (determinístico: vazamento do segredo revela o mapa); sequência embaralhada
  (exige estado e não protege contra inferência por ordem).

## R6 — Serialização contra corrida

- **Decision**: toda mutação (cadastro, alteração, remoção, anexo,
  conclusão) trava a linha da `ActivityInstance` de `sample_definition` com
  `SELECT ... FOR UPDATE` antes de checar o status e escrever.
- **Rationale**: evita que um cadastro concorrente com a conclusão grave
  códigos depois do congelamento, e que duas conclusões simultâneas gerem as
  combinações faltantes duas vezes. CAS duplicado concorrente é resolvido pelo
  índice único parcial `(process_instance_id, cas_number)` → `IntegrityError`
  → 409.
- **Alternatives considered**: trava no `ProcessInstance` (serializa
  atividades paralelas sem necessidade).

## R7 — SDS como `Artifact`

- **Decision**: guardar a SDS em `Artifact` (`key='sample_sds'`) ligado à
  execução da atividade, com o binário em `ATTACHMENTS_DIR` pelas funções de
  `attachment_service` (`store_upload`, `attachment_relpath`,
  `remove_file_best_effort`). Só extensão `pdf`; teto
  `ATTACHMENT_MAX_SIZE_MB`. A substância aponta para o artefato
  (`sds_artifact_id`); substituir exclui logicamente o anterior.
- **Rationale**: reaproveita o armazenamento e a validação da Spec 016. Não
  existe rota genérica de download de `Artifact`: o download da SDS só existe
  na rota nova, que exige a concessão de edição (R3).
- **Alternatives considered**: tabela própria de arquivos (duplicaria
  `Artifact`).

## R8 — QR code

- **Decision**: gerar SVG com a biblioteca `segno` (Python puro, sem
  dependências nativas) e devolver como `data:image/svg+xml;base64,...` no
  JSON de cada etiqueta. O conteúdo do QR é a URL do frontend
  `{SAMPLE_QR_BASE_URL}/amostras/{process_id}/frascos/{code}`; a setting nova
  `SAMPLE_QR_BASE_URL` usa como padrão a primeira origem de
  `AUTH_ALLOWED_ORIGINS`.
- **Rationale**: o usuário decidiu que o backend entrega dados e imagem e o
  frontend imprime. A URL aponta para o frontend porque um celular que abre a
  URL da API não envia o token; o frontend autentica e chama
  `GET /processes/{id}/samples/vials/{code}`. O caminho só carrega
  identificador do processo e código cego (FR-016, FR-017).
- **Ponto a combinar com o frontend**: o caminho `/amostras/{process_id}/frascos/{code}`
  é contrato com o frontend; se o frontend preferir outro, muda só o formato
  da string.
- **Alternatives considered**: `qrcode` (depende de Pillow para PNG);
  devolver só o texto e o frontend desenhar o QR (contraria a decisão do
  usuário).

## R9 — Auditoria sem dados de identidade

- **Decision**: eventos `SAMPLE_SUBSTANCE_REGISTERED`,
  `SAMPLE_SUBSTANCE_UPDATED`, `SAMPLE_SUBSTANCE_REMOVED`, `SAMPLE_SDS_UPLOADED`,
  `SAMPLE_SDS_DOWNLOADED`, `SAMPLE_CODES_GENERATED` e
  `SAMPLE_DEFINITION_COMPLETED`, todos com `activity_run_id` da execução.
  `context_data` guarda só `substance_id`, contagens e ids de laboratório;
  nunca nome químico, CAS, lote nem código cego.
- **Rationale**: a timeline (`GET /processes/{id}/timeline`) mostra eventos de
  execução a quem vê a atividade (`_events_of_visible_activities`), e admin e
  BraCVAM veem esta atividade. Guardar só identificadores opacos cumpre
  FR-025 sem filtro novo na timeline.
- **Alternatives considered**: esconder os eventos da timeline para quem não
  edita (regra nova na timeline só para esta atividade).

## R10 — Congelamento na conclusão

- **Decision**: `POST /processes/{id}/samples/complete` valida (≥ 1
  substância, toda substância com SDS, ≥ 1 laboratório), gera combinações
  faltantes, exclui logicamente códigos de laboratórios sem designação ativa,
  chama `_complete_activity_run` e `_advance_dependent_activities`. Depois
  disso, toda mutação recebe 409 porque a atividade não está `IN_PROGRESS`.
- **Rationale**: o estado "congelado" é o próprio `COMPLETED` da atividade;
  não há coluna nova.
- **Alternatives considered**: flag `frozen` na substância (redundante com o
  status da atividade).

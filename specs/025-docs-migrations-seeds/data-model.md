# Data Model: Spec 025 — Baseline de Produção e Ciclo de Vida de Seeds

## 1. Entidades de Governança do Baseline (Produção)

As entidades abaixo compõem o catálogo permanente do sistema e são provisionadas exclusivamente pelo script de baseline (`pivma.bootstrap_system`):

### AccessProfile (Perfis de Acesso Globais)
- **Tabela**: `access_profiles`
- **Campos**:
  - `id`: UUID (chave primária)
  - `system_key`: String única (`administrator`, `bracvam`)
  - `name`: String (`Administrador`, `BraCVAM`)
  - `description`: String descritiva
  - `deleted_at`: Timestamp (soft-delete, nulo em produção)
- **Regras de Negócio**:
  - Apenas `administrator` e `bracvam` são perfis globais ativos. Usuários sem perfil global assumem automaticamente o papel `default` (Padrão).

### Permission (Catálogo de Permissões do Sistema)
- **Tabela**: `permissions`
- **Campos**:
  - `id`: UUID (chave primária)
  - `code`: String única (código semântico)
  - `description`: String descritiva
- **Catálogo Canônico (15 permissões)**:
  1. `rbac.read`: Consultar o estado do RBAC.
  2. `rbac.profiles.manage`: Gerir perfis e suas permissões.
  3. `rbac.assignments.manage`: Gerir atribuições de perfis.
  4. `users.list`: Listar usuários cadastrados.
  5. `users.manage`: Cadastrar e atualizar usuários.
  6. `affiliations.manage`: Gerenciar afiliações institucionais.
  7. `process.participants.manage`: Gerenciar designações de participantes em métodos.
  8. `triage.review`: Triagem inicial de propostas.
  9. `triage.evaluate`: Avaliação técnica da proposta.
  10. `triage.decide`: Decisão formal de aprovação/rejeição.
  11. `triage.feedback`: Registro de pareceres por critério.
  12. `ai.evaluations.configure`: Parametrizar esteiras de IA e regras assistidas.

### AccessProfilePermission (Composição Perfil-Permissão)
- **Tabela**: `access_profile_permissions`
- **Campos**:
  - `id`: UUID
  - `profile_id`: UUID (FK `access_profiles.id`)
  - `permission_id`: UUID (FK `permissions.id`)
- **Regras de Associação Canônicas**:
  - `administrator`: Possui associação a todas as 12 permissões do catálogo.
  - `bracvam`: Possui associação a `triage.review`, `triage.evaluate`, `triage.decide`, `triage.feedback` e permissões de consulta de processo.

### ProcessTemplate / FormTemplate (Templates Canônicos)
- **Tabelas**: `process_templates`, `process_template_versions`, `form_templates`, `form_fields`
- **Origem de Dados**: Arquivos YAML declarativos em `src/pivma/templates_data/` sincronizados via `bootstrap_all_templates`.
- **Templates Oficiais (Fase 1)**:
  - `pre_validated_method`: Método Pré-Validado.
  - `scope_extension`: Extensão de Escopo.
  - `me_too_validation`: Validação Me-Too.
  - `validated_method_dossier`: Método Validado - Dossiê.
  - `proof_of_concept`: Prova de Conceito - Formulário Preliminar.

---

## 2. Entidades de Demonstração e Testes (Ambiente Dev/Test)

Estas entidades **NUNCA** devem ser geradas em ambiente de produção:

### ProcessInstance de Demonstração
- **Tabela**: `process_instances`
- **Regra de Namespace**:
  - Todo processo gerado por scripts de seed possui título iniciado com prefixo rastreável:
    - `[DEMO 1]`, `[DEMO 2]`, `[DEMO 3]`, `[DEMO 4]`, `[DEMO 5]`
    - `[DEMO KANBAN] #...`
    - `[DEMO 10] Atualização de submissão`
    - `[DEMO 11] Ciclo de vida`
- **Regra de Limpeza (`--clean`)**:
  - O comando de limpeza executa exclusão/expurgo estritamente nas instâncias cujo título corresponda a `title LIKE '[DEMO%'`, garantindo isolamento total em relação a dados reais.

### Usuários de Demonstração
- **Tabela**: `users`
- **Contas de Teste**:
  - `admin` (Administrador / BraCVAM)
  - `proponent_user` (Proponente)
  - `triage_evaluator` (Avaliador Técnico)
  - `kanban_demo_bracvam` (BraCVAM de Carga)
  - `kanban_demo_padrao_a` / `kanban_demo_padrao_b` (Usuários de Cargos Cruzados)

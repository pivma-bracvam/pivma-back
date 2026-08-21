# Research: Estrutura Base de Processos e Fase 1: Submissão e Triagem

**Feature**: 004-process-submission-triage  
**Date**: 2026-08-21  
**Spec**: [spec.md](spec.md)

## 1. Abstração de Processos e Separação entre Template e Execução

### Contexto
O PIVMA necessita suportar múltiplos pipelines de validação científica que compartilham a mesma espinha dorsal conceitual (Submissão, Triagem, Planejamento, Execução Interlaboratorial, Revisão Técnica, Consolidação e Deliberação). A primeira entrega opera exclusivamente a **Fase 1: Submissão e Triagem**, mas o modelo de dados e as entidades de persistência devem acomodar todo o ciclo sem refatorações estruturais posteriores.

### Decisão
Separar estritamente a definição estrutural da execução concreta através da hierarquia:
```text
ProcessTemplate
    ↓
ProcessTemplateVersion
    ↓
ProcessInstance
    ├── Phase
    ├── ActivityInstance
    │       ↓
    │   ActivityRun (múltiplas execuções possíveis)
    │       ├── Task
    │       ├── FormInstance
    │       │       └── FieldReview (avaliação de campo na triagem)
    │       └── Artifact
    ├── Assignment (papéis locais)
    ├── ActivityDependency (pré-condições)
    ├── Decision (pareceres de aprovação/rejeição/diligência)
    └── AuditEvent (trilha imutável)
```
- **Rationale**: Ao instanciar um processo, ele se vincula a uma `ProcessTemplateVersion` imutável. Atualizações futuras no template criam uma nova versão sem afetar instâncias em andamento.
- **Alternativas rejeitadas**:
  - *Hardcoded Workflow*: Codificar a sequência de fases/atividades apenas como código em rotas sem tabelas de template tornaria inviável o suporte aos pipelines 2 e 3 e ao versionamento de processos.
  - *Generic Workflow Engine configurável por interface (estilo Camunda/BPMN)*: Complexidade desnecessária e risco de introduzir bugs conceituais; o domínio possui fluxos padronizados onde templates declarativos versionados atendem com muito mais robustez e simplicidade.

---

## 2. Modelo de Reexecução e Preservação de Histórico (`ActivityRun`)

### Contexto
Quando uma submissão é avaliada na triagem e o triador identifica pendências (diligência/ajustes), ou quando ocorrem falhas em atividades posteriores, o sistema não deve sobrescrever o registro anterior nem realizar rollback destrutivo.

### Decisão
Modelar a execução através de `ActivityRun` dentro de cada `ActivityInstance`:
- A primeira submissão ocorre em `ActivityRun` com `run_number = 1` e status `COMPLETED`.
- A triagem avalia a submissão. Ao emitir uma `Decision` do tipo `NEEDS_REVISION`, uma nova execução `ActivityRun` com `run_number = 2` é criada na atividade de submissão.
- Os dados do formulário anterior (`FormInstance` do Run 1) são clonados/carregados como ponto de partida para o novo `FormInstance` do Run 2.
- A `ActivityRun` anterior permanece intacta e consultável na auditoria e timeline.
- **Rationale**: Garante conformidade com o princípio de "Histórico completo $\neq$ Evidência consolidada", preservando todas as tentativas e pareceres emitidos.
- **Alternativas rejeitadas**:
  - *Reabrir o status do mesmo registro*: Perde a foto do que foi submetido no momento da triagem original e impede a reconstituição fiel da trilha regulatória.

---

## 3. Formulários Dinâmicos e Avaliação Campo a Campo (`FieldReview`)

### Contexto
Cada tipo de processo possui campos específicos no formulário de submissão (título, método de referência, escopo, objetivos, arquivos anexados, etc.). Durante a triagem, o triador inspeciona esses campos individualmente antes de emitir o parecer global.

### Decisão
Adotar um modelo de dados relacional e tipado para formulários:
- `FormTemplate`: Agrupa a definição de um formulário versionado.
- `FormField`: Declara cada campo (`field_key`, `label`, `field_type`, `required`, `order_index`, `validation_rules` em JSONB, `options` em JSONB).
- `FormInstance`: Representa o preenchimento concreto vinculado a um `ActivityRun`.
- `FormValue`: Armazena o valor do campo (`text_value`, `numeric_value`, `boolean_value`, `date_value`, `file_id`/`json_value`).
- `FieldReview`: Representa a avaliação de um campo específico realizada pelo triador (`status`: `CONFORME`, `NAO_CONFORME`, `OBSERVACAO`, `comments`: texto, `reviewed_by`: usuário, `reviewed_at`: data).
- **Rationale**: A separação entre `FormValue` e `FieldReview` mantém os dados brutos submetidos pelo proponente isolados dos apontamentos do revisor, permitindo comparar versões e gerar relatórios claros de pendências.
- **Alternativas rejeitadas**:
  - *Armazenar todo o formulário em um único JSONB não-tipado*: Dificulta validações determinísticas no banco, criação de constraints e auditoria granular de avaliações campo a campo.

---

## 4. Templates Declarativos e Semente Inicial (YAML)

### Contexto
O usuário aprovou o uso de arquivos declarativos YAML para inicializar e versionar templates de processo e formulários no sistema.

### Decisão
Criar um módulo de carregamento declarativo (`pivma.core.process_seed` ou similar):
- Arquivos YAML estruturados sob `src/pivma/templates_data/` ou carregados via comando CLI/startup (ex.: `full_validation_v1.yaml`).
- O schema YAML define: metadados do template, fases, atividades, pré-condições/dependências, papéis atribuíveis e definições completas de formulários e campos.
- O carregador insere ou valida a existência do `ProcessTemplate` e `ProcessTemplateVersion` no banco de dados garantindo idempotência.
- **Rationale**: Facilita a manutenção, versionamento via git e pavimenta o caminho para a futura importação/conversão de formulários existentes.
- **Alternativas rejeitadas**:
  - *Inserção via migration puramente em SQL manual*: Dificulta a evolução e leitura dos formulários compostos por dezenas de campos.

---

## 5. Máquina de Estados e Motor de Dependências

### Contexto
As atividades não progridem apenas por ordem numérica linear. Uma atividade só se torna `READY` quando suas pré-condições (`ActivityDependency`) são satisfeitas. Caso contrário, permanece `BLOCKED` com justificativa explicável.

### Decisão
Implementar um avaliador determinístico de dependências no serviço de processo:
- **Estados de ProcessInstance**: `DRAFT`, `SUBMISSION`, `TRIAGE`, `PLANNING`, `CLOSED`.
- **Estados de ActivityInstance / ActivityRun**: `BLOCKED`, `READY`, `IN_PROGRESS`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Estados de Task**: `UNASSIGNED`, `ASSIGNED`, `IN_PROGRESS`, `SUBMITTED`, `COMPLETED`, `CANCELLED`.
- **Avaliação de Dependência**:
  - Ao concluir um `ActivityRun` com sucesso, o sistema recalcula as atividades dependentes da instância.
  - Para a Fase 1: A atividade de Submissão inicia `READY` (ou `IN_PROGRESS`). A atividade de Triagem depende da conclusão (`COMPLETED`) da atividade de Submissão. Se a submissão não foi concluída, a Triagem fica `BLOCKED` ("Aguardando conclusão da Submissão da Proposta").
- **Rationale**: Regra simples, determinística e explicável, sem sobrecarga de um motor BPMN externo.

---

## 6. Controle de Acesso e Papéis Locais (`Assignment`)

### Contexto
Além dos perfis globais do RBAC existente (`Admin`, `Gestor`, `Pesquisador`, etc.), a instância de processo possui atribuições locais de responsabilidade:
- `PROPONENT`: O usuário que iniciou a submissão e responde por ela.
- `TRIAGE_LEAD` / `GESTOR`: Responsável por conduzir a revisão e deliberação de triagem.

### Decisão
A entidade `Assignment` vincula `(process_instance_id, user_id, role_key)` com auditoria (`assigned_by`, `assigned_at`, `revoked_at`).
- O endpoint de submissão associa automaticamente o usuário autenticado como `PROPONENT` daquela instância.
- Membros do Grupo Gestor têm permissão global para atuar na triagem ou podem ser atribuídos especificamente como responsáveis.
- **Rationale**: Desacopla o RBAC global das instâncias operacionais e permite rastrear quem atuou em cada etapa.


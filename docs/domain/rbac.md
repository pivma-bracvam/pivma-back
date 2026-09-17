# Matriz de Governança RBAC: Perfis Globais vs Cargos Locais

A PIVMA adota um modelo híbrido de autorização desenhado sob a **Spec 018** e **Spec 023**:
1. **Perfis Globais de Plataforma**: Determinam a visibilidade geral do usuário na plataforma.
2. **Cargos Contextuais em Métodos (`Assignment`)**: Determinam o que o usuário pode fazer dentro de um método específico.

---

## 🌐 1. Perfis Globais de Plataforma

Existem apenas dois perfis globais atribuíveis no sistema. Usuários comuns operam no perfil implícito `default`:

| Perfil Global (`system_key`) | Escopo de Visibilidade | Responsabilidades Principais |
| :--- | :--- | :--- |
| `administrator` | **Total (Plataforma inteira)** | Gestão de contas de usuários, parâmetros de IA, sincronização de templates e auditoria geral. |
| `bracvam` | **Total (Todos os métodos)** | Condução da triagem técnica, emissão de pareceres, decisão de admissibilidade e acompanhamento de todos os estudos no Kanban. |
| *(nenhum - Padrão / `default`)* | **Restrito (Apenas métodos designados)** | Pesquisadores, proponentes e laboratórios. Só enxergam métodos onde possuem designação ativa. |

---

## 🎯 2. Cargos Contextuais em Processos (`Assignment.role_key`)

Dentro de cada processo (`ProcessInstance`), os usuários recebem papéis através de designações (`Assignment`). Um mesmo usuário pode ter papéis diferentes em métodos diferentes:

```mermaid
flowchart TD
    User[Usuário: Dra. Ana (Perfil Global: Padrão)]
    User -->|Cargo: Proponente| ProcA[Método A: Ensaio BCOP]
    User -->|Cargo: Gestor do Estudo| ProcB[Método B: Teste Me-Too]
    User -.->|Sem acesso / Invisível| ProcC[Método C: Outro Laboratório]
```

### Catálogo de Papéis Locais de Processo

| Papel (`role_key`) | Quando atua | Atividades Permitidas |
| :--- | :--- | :--- |
| `proponent` | Fase 1 (Submissão) | Preencher formulário, anexar POPs, acompanhar pré-avaliação por IA e submeter rascunhos. |
| `group_manager` | Fase 2 (Planejamento) | Coordena o estudo de validação, elabora cronogramas e indica laboratórios. |
| `study_manager` | Fase 2 (Execução) | Gerencia a condução dos testes experimentais e coleta de dados brutos. |
| `participating_laboratory` | Fase 2 (Execução) | Laboratório que executa o método às cegas conforme o protocolo aprovado. |
| `reviewer` / `ad_hoc_evaluator` | Fase 1 e 2 | Especialistas convidados para emitir parecer técnico cego ou aberto. |
| `statistical_analyst` | Fase 2 (Análise) | Avalia a reprodutibilidade interlaboratorial e desvios-padrão dos ensaios. |

---

## 🛡️ 3. Catálogo de Permissões Canônicas (`permissions`)

As permissões ativas que controlam as rotas do backend são:

- `users.list`: Listar usuários cadastrados na plataforma.
- `users.manage`: Ativar, editar e desativar contas de usuários.
- `rbac.read`: Consultar a composição de perfis e permissões.
- `rbac.profiles.manage`: Criar e alterar perfis de acesso.
- `rbac.assignments.manage`: Atribuir perfis a usuários.
- `affiliations.manage`: Gerenciar afiliações institucionais de usuários.
- `process.participants.manage`: Designar participantes e laboratórios em processos.
- `triage.review`: Conduzir a triagem de métodos e registrar pareceres técnicos.
- `ai.evaluations.configure`: Configurar prompts, critérios e modelos das esteiras de IA.
- `form_templates.manage`: Editar a definição de formulários de processo (campos, nome, descrição) — concedida ao BraCVAM além do Administrador (Issue #39).

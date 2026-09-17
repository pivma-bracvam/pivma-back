# Arquitetura de Seeds, Perfis e Reset

Para garantir uma colaboração fluida e sem atritos entre o backend e o time de frontend (mesmo em fusos horários diferentes), a PIVMA separa rigidamente o **Catálogo de Produção** das **Cargas de Demonstração**.

---

## 🏛️ A Regra de Ouro: Produção vs Demonstração

| Tipo de Dado | Onde reside | Como é carregado | O que contém |
| :--- | :--- | :--- | :--- |
| **Baseline de Produção** | `src/pivma/bootstrap_system.py` | Executado no `entrypoint.sh` ou `python -m pivma.bootstrap_system` | Perfis globais ativos (`administrator`, `bracvam`), catálogo canônico de permissões e templates oficiais de validação (`templates_data/`). **Zero processos ou propostas falsas.** |
| **Dados de Demonstração** | `scripts/seeds/` | Executado sob demanda via CLI: `python -m scripts.seeds` | Usuários fictícios (`proponent_user`, `triage_evaluator`), processos de exemplo e avaliações de teste. |

---

## 🎮 Comandos da CLI de Seeds

O ponto de entrada oficial para carregar e gerenciar dados de teste é:

```bash
uv run python -m scripts.seeds [OPÇÕES]
```

### 1. Carga Padrão de Desenvolvimento (`--profile dev`)
Recomendado para o trabalho diário da equipe de frontend e backend:

```bash
uv run python -m scripts.seeds --profile dev
```
* Cria os usuários padrão de teste.
* Instancia os 5 processos canônicos da Fase 1.
* Coloca 1 processo em triagem técnica com pré-avaliação por IA simulada.
* Cria apenas **6 processos distribuídos no Kanban** (em vez dos 300 anteriores).
* **Tempo de execução**: < 5 segundos.

### 2. Carga de Estresse do Kanban (`--profile kanban`)
Utilize este comando apenas quando precisar testar paginação, rolagem infinita ou performance da UI com grande volume de dados:

```bash
# Gera os ~300 processos para teste de estresse
uv run python -m scripts.seeds --profile kanban --count 300
```

### 3. Limpeza Segura do Banco (`--clean`)
Se a interface estiver poluída ou você quiser reiniciar os testes do zero:

```bash
uv run python -m scripts.seeds --clean
```
* **O que ele apaga**: Apenas processos cujo título comece com `[DEMO` e vínculos associados a esses testes.
* **O que ele preserva**: Todas as migrações, perfis do sistema, permissões e templates canônicos permanecem intactos.

---

## 🔑 Contas de Teste Pré-Configuradas

Após rodar o seed `dev`, as seguintes credenciais ficam disponíveis:

| Usuário | Senha | Perfil Global | Propósito |
| :--- | :--- | :--- | :--- |
| `admin` | `Password123!` | Administrador / BraCVAM | Gestão de templates, usuários e triagem de métodos |
| `proponent_user` | `Password123!` | Padrão | Submissão de propostas e acompanhamento de pré-avaliação |
| `triage_evaluator` | `Password123!` | BraCVAM | Parecer técnico e decisão na triagem |
| `kanban_demo_padrao_a` | `KanbanDemo@123456` | Padrão | Demonstração de cargos cruzados (Proponente em A, Gestor em B) |

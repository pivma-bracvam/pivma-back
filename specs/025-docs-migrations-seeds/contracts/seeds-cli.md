# Contrato de Interface CLI: `scripts/seeds/runner.py`

Ponto de entrada unificado para carga, gestão e limpeza de dados de demonstração:

```bash
uv run python -m scripts.seeds [OPÇÕES]
```

## Opções de Linha de Comando

| Argumento | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `--profile` | String (`dev`, `kanban`, `all`) | `dev` | Perfil de carga a ser executado. |
| `--count` | Inteiro | 6 (dev) / 300 (kanban) | Quantidade de processos a serem gerados no Kanban. |
| `--clean` | Flag booleana | False | Executa a limpeza segura de todos os dados de demonstração sem semear nada. |
| `--reset` | Flag booleana | False | Executa `--clean` seguido da semeadura do perfil selecionado. |

## Perfis Suportados

### 1. Perfil `dev` (Happy Path Rápido)
- **Comando**: `uv run python -m scripts.seeds --profile dev` (ou simplesmente `uv run python -m scripts.seeds`)
- **Ações**:
  - Garante que `pivma.bootstrap_system` foi executado.
  - Cria usuários de teste: `admin`, `proponent_user`, `triage_evaluator`.
  - Instancia 5 processos canônicos da Fase 1 (1 para cada template publicado).
  - Instancia 1 processo em triagem técnica com pré-avaliação por IA simulada.
  - Instancia apenas **6 processos** distribuídos no Kanban (2 recém-submetidos, 2 em triagem, 1 atrasado, 1 concluído).
- **Tempo Médio**: < 5 segundos.
- **Processos Totais**: ~6 processos ativos.

### 2. Perfil `kanban` (Carga de Estresse)
- **Comando**: `uv run python -m scripts.seeds --profile kanban [--count N]`
- **Ações**:
  - Gera a massa de 300 processos (ou N customizado) com marcador `[DEMO KANBAN]` para teste de paginação e performance.

### 3. Opção `--clean` (Expurgo Seguro)
- **Comando**: `uv run python -m scripts.seeds --clean`
- **Ações**:
  - Remove/expurga todas as instâncias de processos onde `title LIKE '[DEMO%'`.
  - Remove atribuições e execuções vinculadas a esses processos.
  - **Preserva integralmente**: Perfis, permissões e templates canônicos do baseline de produção.

# Quickstart: Validação da Spec 025

Este guia contém os comandos para testar e validar de ponta a ponta a Spec 025: documentação MkDocs, migrações DDL puras, provisionamento de produção e seeds de demonstração.

---

## Cenário 1: Construção e Visualização da Documentação MkDocs

1. **Instalar dependências de documentação**:
   ```bash
   uv sync --group docs
   ```

2. **Compilar a documentação em modo estrito (zero warnings)**:
   ```bash
   uv run mkdocs build --strict
   ```
   *Resultado esperado*: Diretório `site/` gerado com sucesso sem nenhum link quebrado.

3. **Iniciar o servidor de documentação local**:
   ```bash
   uv run mkdocs serve
   ```
   *Resultado esperado*: Acesso a `http://localhost:8000` (ou porta configurada) exibindo o portal completo em português com diagramas Mermaid renderizados.

---

## Cenário 2: Validação de Migrações DDL Puras

1. **Executar migrações do zero em banco limpo**:
   ```bash
   uv run alembic upgrade head
   ```
   *Resultado esperado*: Todas as 17 migrações executam com sucesso.

2. **Verificar que as tabelas de catálogo estão vazias antes do bootstrap**:
   ```sql
   SELECT count(*) FROM access_profiles; -- Retorna 0
   SELECT count(*) FROM permissions;      -- Retorna 0
   ```

---

## Cenário 3: Provisionamento de Produção (`bootstrap_system`)

1. **Executar o bootstrap de sistema**:
   ```bash
   uv run python -m pivma.bootstrap_system
   ```
   *Resultado esperado*:
   - Cria os perfis `administrator` e `bracvam`.
   - Cria as 12 permissões oficiais do catálogo.
   - Sincroniza os 5 templates canônicos da Fase 1 (`templates_data/`).
   - Zero processos criados.

2. **Validar idempotência (execução consecutiva)**:
   ```bash
   uv run python -m pivma.bootstrap_system
   ```
   *Resultado esperado*: Executa sem nenhum erro, sem duplicar perfis ou permissões.

---

## Cenário 4: Seeds de Demonstração e Limpeza

1. **Executar o seed padrão de desenvolvimento**:
   ```bash
   uv run python -m scripts.seeds --profile dev
   ```
   *Resultado esperado*: Conclui em < 5 segundos, gerando 5 processos padrão e apenas 6 processos no Kanban.

2. **Executar a limpeza de dados de teste**:
   ```bash
   uv run python -m scripts.seeds --clean
   ```
   *Resultado esperado*: Todos os processos `[DEMO%` são expurgados. Perfis e templates de produção permanecem intactos.

3. **Executar a carga de estresse do Kanban (apenas sob demanda)**:
   ```bash
   uv run python -m scripts.seeds --profile kanban --count 300
   ```
   *Resultado esperado*: Gera os 300 processos para teste de estresse apenas quando solicitado.

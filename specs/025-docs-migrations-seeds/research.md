# Research & Technical Decisions: Spec 025

## 1. Documentação de Plataforma: MkDocs Material

### Decisão
Adotar o **MkDocs com o tema Material for MkDocs (`mkdocs-material`)** como a ferramenta oficial de documentação viva, arquitetural e de integração do PIVMA.

### Racional
- **Sintaxe e Manutenibilidade**: Utiliza Markdown puro compatível com GitHub Flavored Markdown e Mermaid (`pymdownx.superfences`), permitindo versionamento junto com o código no Git.
- **Suporte Multilíngue e Pesquisa Local**: Suporte nativo a português brasileiro (`language: pt-BR`) com indexação de busca local offline no navegador (sem necessidade de backend de busca externo).
- **Consumo do Frontend em Fuso Horário Distinto**: Permite renderizar diagramas de sequência, fluxos de máquina de estados, tabelas consolidadas de RBAC e recipes de consumo de endpoints.
- **Integração com o Ciclo de Vida**: Pode ser gerado localmente com recarregamento em tempo real (`mkdocs serve`) ou compilado em HTML estático (`mkdocs build --strict`) para publicação em container ou GitHub Pages.

### Alternativas Consideradas
- **Sphinx / ReadTheDocs**: Mais pesado, utiliza reStructuredText por padrão e possui curva de aprendizado maior para desenvolvedores de frontend.
- **Docusaurus**: Exige ambiente Node.js / React dentro do repositório backend, adicionando dependência de ferramentas JavaScript desnecessárias no projeto FastAPI.
- **Manter apenas o Swagger (`/docs`)**: Insuficiente para guias conceituais, fluxos de processo de negócio, matriz de RBAC e instruções de onboarding.

---

## 2. Separação Estrita de DDL e DML no Alembic

### Decisão
Remover todos os `op.bulk_insert` e manipulações de dados de domínio das 7 migrações do Alembic (`c1e4a9f8b312`, `5e31a8c7d204`, `6f2c9a1d4e70`, `7a3e1c9b4d82`, `8c5e7a1b9d02`, `8b701d7bfeae`, `d3f9a1c47b28`), mantendo as migrações restritas a DDL (Data Definition Language).

### Racional
- **Anti-Pattern de Migrações com Dados**: Misturar criação de tabelas e inserção de registros estáticos com UUIDs hardcoded gera inconsistências durante reexecuções, dificulta rollbacks e quebra a portabilidade entre bancos de desenvolvimento, homologação e produção.
- **Princípio de Responsabilidade Única**: O Alembic gerencia o esquema físico do banco (tabelas, colunas, chaves estrangeiras, índices e tipos). O provisionamento de catálogo do sistema pertence à aplicação.
- **Adequação aos Padrões 12-Factor App**: O deploy executa a migração estrutural (`alembic upgrade head`) seguida pelo provisionamento idempotente do baseline de sistema.

### Alternativas Consideradas
- **Criar uma nova migração apagando os dados antigos**: Não resolveria o problema em bancos novos que executam as migrações desde a primeira versão, onde os inserts continuariam sendo executados.
- **Deixar as migrações antigas e só mudar as novas**: Manteria o legado corrompendo bases recém-criadas e duplicando lógicas de inserção.

---

## 3. Provisionamento de Sistema em Produção (`bootstrap_system`)

### Decisão
Criar o módulo `src/pivma/bootstrap_system.py` que executa as seguintes operações em transação atômica e estritamente idempotente:
1. **Perfis Oficiais**: Garante a existência dos perfis `administrator` (Administrador) e `bracvam` (BraCVAM).
2. **Catálogo de Permissões**: Garante a existência de todas as 15 permissões oficiais (RBAC, Users, Affiliations, Participants, Triage, AI, etc.).
3. **Composição Perfil-Permissão**: Garante a associação das permissões correspondentes aos perfis ativos.
4. **Templates e Formulários Oficiais**: Invoca `bootstrap_all_templates` sincronizando os templates canônicos da pasta `templates_data/`.
5. **Primeiro Administrador (Configurável)**: Se `INITIAL_ADMIN_EMAIL` e `INITIAL_ADMIN_PASSWORD` estiverem definidos, assegura que a conta exista e possua o perfil Administrador.

### Racional
- **Idempotência**: Todas as operações utilizam consultas de existência prévia (`select ... where`) antes de inserir, garantindo que o comando possa ser executado centenas de vezes sem efeitos colaterais.
- **Segurança e Pureza**: Nenhuma entidade de demonstração (processos, propostas, avaliações) é criada. O banco de produção permanece limpo.

---

## 4. Reestruturação e Governança dos Seeds de Demonstração

### Decisão
Criar uma CLI unificada em `scripts/seeds/runner.py` com pontos de entrada por perfil:
1. `--profile dev` (Default): Cria contas de teste (`admin`, `proponent_user`, `triage_evaluator`), 5 processos canônicos (1 para cada template da Fase 1) e **apenas 6 processos representativos no Kanban**.
2. `--profile kanban` (ou `--count 300`): Carga de estresse opcional para validação de performance/virtualização do Kanban.
3. `--clean`: Expurgador seguro que remove apenas instâncias com prefixo `[DEMO` e usuários mockados, preservando o baseline de produção.
4. **Remoção de Deleções Cruzadas**: Excluir cláusulas `where title not in (...)` de `seed_forms.py` e `seed_triage.py`.

### Racional
- Desafoga imediatamente a máquina do frontend, que antes recebia 300 processos em qualquer execução de seed.
- Elimina o problema de scripts apagando registros criados por outros scripts.

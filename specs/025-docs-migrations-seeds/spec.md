# Feature Specification: Documentação MkDocs, Migrações DDL Puras e Separação de Seeds

**Feature Branch**: `025-docs-migrations-seeds`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Quero uma grande refatoração na plataforma, começando com a implementação de uma documentação com MKDOCS. Seguido de uma desestruturação do código de seeds: Notei que existem inserts que ocorrem dentro das migrações, não quero que isso ocorra, crie um script de seed que roda separadamente, sempre junto com o entrypoint. Separe os scripts de seed reais que vão pra produção do que é utilizado para demos."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consulta a Documentação Técnica e Guias de Integração Viva (Priority: P1)

Como desenvolvedor de frontend trabalhando de forma assíncrona (ou novo integrante da equipe técnica), quero acessar um portal de documentação estruturado, navegável e consolidado (via MkDocs), contendo o ciclo de vida dos processos, a governança de perfis/cargos, as regras de negócio de funcionalidades agregadas (como o Kanban de pendências) e os guias de consumo da API, para que eu possa desenvolver interfaces completas com autonomia, sem bloqueios de fuso horário e sem depender de reuniões síncronas.

**Why this priority**: É a fundação para a colaboração assíncrona eficiente entre equipes multidisciplinares e a fonte viva da verdade do sistema consolidado.

**Independent Test**: Subir o servidor de documentação localmente e navegar por todas as seções essenciais (Onboarding, Domínio, Funcionalidade Kanban, Receitas de Frontend), confirmando que um desenvolvedor consegue implementar o consumo dos endpoints guiando-se exclusivamente pela documentação.

**Acceptance Scenarios**:
1. **Given** um desenvolvedor que acabou de clonar o projeto, **When** ele executa o comando de documentação, **Then** o portal MkDocs é servido localmente com interface moderna, pesquisa funcional e suporte a diagramas de fluxo.
2. **Given** a especificação da funcionalidade do Kanban, **When** o desenvolvedor de frontend consulta a seção correspondente, **Then** ele encontra o propósito de negócio, os filtros suportados, o formato do retorno com contadores de coluna e o link para a tela de demonstração como referência.
3. **Given** a necessidade de entender a diferença entre perfis globais e cargos locais de processo, **When** o leitor acessa o guia de RBAC, **Then** ele encontra uma matriz clara e consolidada das permissões vigentes.

---

### User Story 2 - Execução de Migrações Estritamente Estruturais / DDL (Priority: P1)

Como engenheiro de software ou operador de infraestrutura, quero que todas as migrações do banco de dados (Alembic) sejam estritamente estruturais (DDL puro), criando e alterando apenas tabelas, colunas, chaves, enums e índices, sem inserir linhas ou dados de catálogo no banco, para garantir que as migrações sejam determinísticas, reversíveis e livres de conflitos de chave primária entre ambientes.

**Why this priority**: A mistura de inserção de dados em migrações DDL gera corrupção de catálogo, quebra upgrades/downgrades e viola as boas práticas de engenharia de software e 12-factor apps.

**Independent Test**: Executar `alembic upgrade head` em uma base vazia e verificar que o schema de tabelas foi criado perfeitamente, mas as tabelas de dados permanecem vazias até o provisionamento explícito.

**Acceptance Scenarios**:
1. **Given** um banco de dados novo, **When** `alembic upgrade head` é executado, **Then** todas as tabelas e restrições são criadas sem nenhuma chamada de `bulk_insert` de dados de negócio ou permissões.
2. **Given** a necessidade de reverter uma migração (`alembic downgrade`), **When** o comando é executado, **Then** as alterações de schema são desfeitas sem erros de dependência de dados inexistentes.

---

### User Story 3 - Provisionamento Automático e Idempotente do Baseline de Produção (Priority: P1)

Como operador de sistema ou pipeline de deploy, quero que o container da aplicação execute automaticamente um script de provisionamento de produção (`bootstrap_system`) logo após as migrações no entrypoint, garantindo a existência dos perfis oficiais ativos (`administrator`, `bracvam`), de todas as permissões do sistema e dos templates canônicos de processo, sem inserir nenhum dado fictício de teste.

**Why this priority**: Garante que o ambiente de produção nasça configurado e pronto para operar sem intervenção manual e sem poluição de dados mockados.

**Independent Test**: Executar o script de provisionamento de produção em um banco recém-migrado, verificar a presença dos registros canônicos de governança e reexecutá-lo sucessivas vezes para provar idempotência estrita (sem erros ou duplicações).

**Acceptance Scenarios**:
1. **Given** um banco recém-migrado, **When** o container inicia via `entrypoint.sh`, **Then** as migrações rodam seguidas do provisionamento de sistema, deixando o banco pronto para receber usuários reais.
2. **Given** um banco já provisionado, **When** o provisionamento roda novamente em um reinício de container, **Then** a operação conclui com sucesso mantendo os dados existentes inalterados.
3. **Given** uma execução em produção, **When** o provisionamento conclui, **Then** zero processos de teste, zero formulários preenchidos e zero avaliações fictícias existem no banco de dados.

---

### User Story 4 - Gestão Isolada, Não Destrutiva e Enxuta de Dados de Demonstração (Priority: P2)

Como desenvolvedor de frontend ou backend, quero executar comandos de carga de demonstração com perfis bem definidos (`dev` para o dia a dia, `kanban` para estresse de UI) e dispor de um comando de limpeza segura (`--clean`), sem que um script de seed delete processos criados por outros scripts ou gere centenas de itens indesejados por padrão.

**Why this priority**: Evita o travamento da interface do frontend, elimina o acúmulo de centenas de processos fantasmas e encerra o ciclo de scripts se auto-destruindo.

**Independent Test**: Executar o seed de desenvolvimento (`--profile dev`) e verificar a criação de apenas 5 processos canônicos e 6 itens no kanban; executar `--clean` e verificar a remoção apenas dos dados de teste com preservação integral do baseline de produção.

**Acceptance Scenarios**:
1. **Given** um ambiente recém-provisionado, **When** o desenvolvedor roda o seed padrão de desenvolvimento, **Then** um conjunto mínimo e coerente de usuários e processos de teste é criado em menos de 5 segundos.
2. **Given** um banco de teste carregado, **When** o comando de limpeza (`--clean`) é executado, **Then** apenas os registros identificados com marcadores de demonstração são removidos, mantendo os perfis, permissões e templates de produção intactos.
3. **Given** a necessidade de testar a performance do Kanban com grande volume, **When** o desenvolvedor executa explicitamente `--profile kanban` (ou `--count 300`), **Then** a massa de 300 métodos é gerada sob demanda isoladamente.

---

## Edge Cases

- **Execução repetida do provisionamento**: O provisionamento deve utilizar operações seguras de existência (`IF NOT EXISTS` / busca prévia ou upsert) para tolerar múltiplas inicializações concorrentes de réplicas de aplicação.
- **Banco contendo processos legados de teste com soft-delete**: O comando de limpeza (`--clean`) deve expurgar física ou logicamente apenas os dados marcados com o namespace de teste (`[DEMO%`), sem afetar nenhum processo criado manualmente por usuários.
- **Execução do entrypoint sem conexão inicial com o banco**: O script de inicialização deve falhar imediatamente com código de erro não-zero caso as migrações ou o provisionamento de baseline falhem, impedindo a subida de uma API inconsistente.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE disponibilizar documentação em formato estático navegável gerada via MkDocs com tema Material, abrangendo arquitetura, onboarding, ciclo de vida, RBAC e guias de frontend.
- **FR-002**: A documentação DEVE documentar o Kanban como uma funcionalidade central apoiada pelo endpoint `GET /activities/kanban`, descrevendo seus parâmetros, contadores por coluna e regras de visibilidade.
- **FR-003**: As migrações do Alembic DEVEM conter exclusivamente operações DDL (criação/alteração de tabelas, tipos, índices, restrições e foreign keys), sendo proibida a inserção direta de registros de catálogo via `bulk_insert` nas migrações.
- **FR-004**: O sistema DEVE fornecer um script unificado de provisionamento de produção (`pivma.bootstrap_system`), responsável por criar os perfis ativos oficiais (`administrator`, `bracvam`), o catálogo de permissões e os templates canônicos de processo.
- **FR-005**: O arquivo de entrada do container (`entrypoint.sh`) DEVE executar de forma sequencial e obrigatória: primeiro as migrações DDL e, em seguida, o script de provisionamento de produção.
- **FR-006**: Os scripts de dados de demonstração DEVEM ser segregados em módulo dedicado (`scripts/seeds/`), acessíveis por perfis nomeados via linha de comando (`dev`, `kanban`).
- **FR-007**: O perfil padrão de demonstração (`dev`) NÃO DEVE gerar mais de 10 processos no total do banco de dados.
- **FR-008**: O sistema DEVE disponibilizar uma opção de limpeza (`--clean`) capaz de expurgar todos os dados gerados pelas seeds de demonstração sem corromper o baseline do sistema.
- **FR-009**: Nenhum script de seed de demonstração DEVE executar deleção em massa de processos criados por outros scripts (eliminação de cláusulas `WHERE title NOT IN (...)`).

### Key Entities

- **AccessProfile / Permission**: Entidades de governança do sistema cujo catálogo base passa a ser de responsabilidade exclusiva do provisionador de baseline de produção.
- **ProcessTemplate / FormTemplate**: Modelos e formulários oficiais do BraCVAM provisionados a partir de arquivos declarativos em produção.
- **ProcessInstance (com marcador de teste)**: Instâncias de processos criadas exclusivamente durante cenários de desenvolvimento ou demonstração.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O tempo de inicialização do seed padrão de desenvolvimento (`--profile dev`) deve ser inferior a 5 segundos.
- **SC-002**: O número de processos ativos gerados pelo seed padrão de desenvolvimento deve ser exatamente 6 processos (em vez dos 300 anteriores).
- **SC-003**: 100% das migrações do Alembic executadas em um banco limpo devem concluir sem realizar nenhuma inserção de linhas em tabelas de catálogo.
- **SC-004**: O build da documentação com MkDocs (`mkdocs build --strict`) deve passar com zero alertas e zero links quebrados.
- **SC-005**: Reexecuções consecutivas do script de provisionamento de produção no mesmo banco devem resultar em 0 erros e 0 duplicações de permissões ou perfis.

---

## Assumptions

- O ambiente utiliza `poetry` e `uv` para gestão de pacotes Python no Linux.
- A documentação gerada pelo MkDocs pode ser servida localmente durante o desenvolvimento e opcionalmente empacotada em imagem Docker ou deployada em páginas estáticas (GitHub Pages / Nginx).
- A pasta `demos/` existente permanece como sandbox de referência visual e de teste de chamadas HTTP, complementando a documentação conceitual do MkDocs.

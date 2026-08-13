# Documentação do pi\*VMA

Este arquivo organiza as referências atuais do projeto. Ele não cria uma nova especificação e não substitui as fontes oficiais.

## Caminho de leitura

1. Leia o [Plano de Trabalho da Fase II](plano-de-trabalho-fase-ii.md) para conhecer o escopo oficial, a terminologia e os requisitos RF001 a RF062.
2. Consulte o [guia do protótipo](guia-prototipo.md) para entender telas e fluxos observados nos materiais complementares.
3. Verifique [observações e pendências](observacoes-e-pendencias.md) antes de transformar qualquer ponto ambíguo em requisito.
4. Leia o [README do repositório](../README.md) para instalação, execução, testes e convenções técnicas já registradas.
5. Para uma feature, use os artefatos aprovados em `specs/`, criados pelo fluxo do Spec Kit.

## Mapa de fontes

| Autoridade | Referência | Função | Limitação |
|---|---|---|---|
| Principal | [Plano de Trabalho da Fase II](plano-de-trabalho-fase-ii.md) | Conversão fiel do PDF oficial; registra módulos, requisitos, planejamento e equipe | O PDF original não está versionado neste repositório; ambiguidades foram preservadas |
| Complementar | [Guia inicial do protótipo](guia-prototipo.md) | Consolida vídeos e roteiros e separa conteúdo confirmado, inferências e dúvidas | O protótipo não comprova regras definitivas nem controles efetivos do backend |
| Controle de lacunas | [Observações e pendências](observacoes-e-pendencias.md) | Reúne diferenças entre fontes, ambiguidades e perguntas para a equipe | Não decide os pontos registrados |
| Operacional | [README](../README.md) | Descreve stack, ambiente, comandos, testes e execução com Docker | Reflete o estado técnico atual; não substitui requisitos de negócio |
| Implementação atual | Código, migrações e testes listados abaixo | Confirma o comportamento já implementado e seus contratos de regressão | Não é especificação definitiva do produto |
| Especificação de feature | Futuros artefatos em `specs/` | Delimita requisitos, critérios, plano e tarefas aprovadas para uma mudança | Deve permanecer compatível com as fontes oficiais ou registrar a divergência |

## Referências da implementação atual

| Tema | Referência |
|---|---|
| Criação e composição da aplicação | [`src/pivma/__init__.py`](../src/pivma/__init__.py) |
| Endpoint de exemplo para usuários | [`src/pivma/routers/users.py`](../src/pivma/routers/users.py) |
| Schemas de entrada e saída | [`src/pivma/schemas.py`](../src/pivma/schemas.py) |
| Modelo `User` e `AuditMixin` | [`src/pivma/core/database/models.py`](../src/pivma/core/database/models.py) |
| Sessão assíncrona do banco | [`src/pivma/core/database/__init__.py`](../src/pivma/core/database/__init__.py) |
| Configurações de ambiente | [`src/pivma/core/settings.py`](../src/pivma/core/settings.py) |
| Estado atual da camada de segurança | [`src/pivma/core/security.py`](../src/pivma/core/security.py) |
| Migração inicial de usuários | [`migrations/versions/b72da3430b3e_tabela_base_para_user.py`](../migrations/versions/b72da3430b3e_tabela_base_para_user.py) |
| Teste do endpoint raiz | [`tests/test_app.py`](../tests/test_app.py) |
| Contrato testado de criação de usuário | [`tests/routers/test_user.py`](../tests/routers/test_user.py) |
| Fixtures, banco isolado e factories | [`tests/conftest.py`](../tests/conftest.py) |
| Dependências e comandos do projeto | [`pyproject.toml`](../pyproject.toml) |
| PostgreSQL/pgvector e API em containers | [`compose.yaml`](../compose.yaml) |
| Migrações | [`alembic.ini`](../alembic.ini) e diretório [`migrations/`](../migrations/) |

Esses arquivos devem ser lidos em conjunto antes de alterar o exemplo existente. Os testes registram o contrato atual e devem continuar passando, salvo mudança de comportamento aprovada na especificação.

## Referências do Spec Kit

- Configuração instalada: [`.specify/init-options.json`](../.specify/init-options.json), versão 0.16.2.
- Fluxo base: [`.specify/workflows/speckit/workflow.yml`](../.specify/workflows/speckit/workflow.yml), com as etapas `specify`, `plan`, `tasks` e `implement` e gates de revisão.
- Skills locais: diretório [`.agents/skills/`](../.agents/skills/).
- Constituição: [`.specify/memory/constitution.md`](../.specify/memory/constitution.md). O arquivo ainda é um template sem princípios ratificados.

Na árvore de trabalho atual, `.agents/` e `.specify/` estão cobertos pelo `.gitignore`. Essas referências descrevem a instalação local verificada, mas só estarão disponíveis em outro clone se o Spec Kit também estiver instalado nele.

## Estado e pontos a validar

- **CONFIRMADO:** o repositório usa FastAPI, SQLAlchemy assíncrono, Alembic, PostgreSQL/pgvector, Docker Compose e testes com Pytest/Testcontainers.
- **CONFIRMADO:** a segurança ainda não foi implementada em `src/pivma/core/security.py`.
- **PROPOSTA informada pela equipe:** usar JWT transportado por cookies. Os detalhes de segurança e ciclo de vida dos tokens ainda precisam de especificação.
- **CONFIRMADO:** o remoto contém `main` e `develop`; a nomenclatura `dev` mencionada pela equipe precisa ser alinhada com `develop` antes de definir o fluxo de integração.
- **PENDENTE:** a constituição do Spec Kit ainda não foi preenchida nem ratificada.

## Manutenção

- Atualize o Plano de Trabalho convertido somente a partir de uma nova fonte oficial e preserve a redação original.
- Registre conteúdo observado no protótipo no guia, mantendo as categorias `CONFIRMADO NO MATERIAL`, `INFERÊNCIA` e `DÚVIDA / PONTO A VALIDAR`.
- Registre conflitos, lacunas e perguntas em `observacoes-e-pendencias.md`; não escolha silenciosamente uma das versões.
- Mantenha decisões e critérios específicos de implementação nos artefatos da feature em `specs/`, sem reescrever os documentos-fonte.
- Adicione uma nova referência a este índice apenas quando ela tiver função distinta e rastreável.

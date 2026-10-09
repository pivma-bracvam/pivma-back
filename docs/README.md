# Documentação do pi\*VMA

Este arquivo organiza as referências atuais do projeto. Ele não cria uma nova especificação e não substitui as fontes oficiais.

## Caminho de leitura

1. Leia o [Plano de Trabalho da Fase II](plano-de-trabalho-fase-ii.md) para conhecer o escopo oficial, a terminologia e os requisitos RF001 a RF062.
2. Leia [Observações e pendências](observacoes-e-pendencias.md) para conhecer as decisões formais da equipe e as divergências entre fontes. Elas têm precedência sobre o restante da documentação.
3. Consulte o [guia do protótipo](guia-prototipo.md) apenas como contexto histórico: o protótipo está descontinuado.
4. Leia o [manual](../manual/index.md) para saber o que o sistema já faz; a página [Escopo atual](../manual/explicacao/escopo.md) liga os RF001 a RF062 ao código.
5. Leia o [README do repositório](../README.md) para instalação, execução e testes.
6. Para uma feature, use os artefatos aprovados em `specs/`, criados pelo fluxo do Spec Kit.

## Mapa de fontes

| Autoridade | Referência | Função | Limitação |
|---|---|---|---|
| Decisões da equipe | [Observações e pendências](observacoes-e-pendencias.md) | Decisões formais por issue, divergências entre fontes e pendências | Cada seção vale para a issue indicada; prevalece sobre as demais fontes |
| Principal | [Plano de Trabalho da Fase II](plano-de-trabalho-fase-ii.md) | Conversão fiel do PDF oficial; registra módulos, requisitos, planejamento e equipe | O PDF original não está versionado neste repositório; ambiguidades foram preservadas |
| Histórico | [Guia inicial do protótipo](guia-prototipo.md) | Consolida vídeos e roteiros e separa conteúdo confirmado, inferências e dúvidas | O protótipo está descontinuado e não vale como evidência nem prevalece sobre as decisões da equipe |
| Estado atual | [Manual](../manual/index.md) | Descreve o que o sistema faz hoje: tutoriais, guias, referência da API e explicações | Reflete o código; não substitui requisitos de negócio |
| Operacional | [README](../README.md) | Instalação, comandos, testes e execução com Docker | Não substitui requisitos de negócio |
| Implementação atual | Código, migrações e testes | Confirma o comportamento já implementado e seus contratos de regressão | Não é especificação definitiva do produto |
| Especificação de feature | Artefatos em `specs/` | Delimita requisitos, critérios, plano e tarefas aprovadas para uma mudança | Deve permanecer compatível com as fontes oficiais ou registrar a divergência |

## Referências do Spec Kit

- Configuração instalada: [`.specify/init-options.json`](../.specify/init-options.json), versão 1.0.6.dev0, integração `claude`.
- Fluxo base: [`.specify/workflows/speckit/workflow.yml`](../.specify/workflows/speckit/workflow.yml), com as etapas `specify`, `plan`, `tasks` e `implement` e gates de revisão.
- Skills: [`.agents/skills/`](../.agents/skills/) (`karpathy-guidelines`, `stop-slop`, `testing-methodology`) e [`.claude/skills/`](../.claude/skills/) (`speckit-*` e links para as anteriores).
- Constituição: [`.specify/memory/constitution.md`](../.specify/memory/constitution.md), versão 1.0.0 ratificada em 2026-10-03.

`.specify/`, `.agents/skills/` e `.claude/skills/` são versionados. Ficam fora do git só o estado local (`.specify/feature.json` e `.claude/settings.local.json`).

## Estado e pontos a validar

- **CONFIRMADO:** o repositório usa FastAPI, SQLAlchemy assíncrono, Alembic, PostgreSQL/pgvector, Docker Compose e testes com Pytest/Testcontainers.
- **CONFIRMADO:** a autenticação usa um JWT de até oito horas, transportado pelo cookie `HttpOnly`, `Secure` e `SameSite=Strict` ou, fora do navegador, por `Authorization: Bearer`. Detalhes em [Sessão e segurança](../manual/explicacao/sessao-e-seguranca.md).
- **CONFIRMADO:** o remoto contém `main` e `develop`; as entregas vão para `develop`.

## Manutenção

- Atualize o Plano de Trabalho convertido somente a partir de uma nova fonte oficial e preserve a redação original.
- Não acrescente conteúdo novo ao guia do protótipo: ele é histórico.
- Registre conflitos, lacunas e decisões em [Observações e pendências](observacoes-e-pendencias.md) e na spec da feature afetada, e pergunte à equipe; não escolha silenciosamente uma das versões.
- Mantenha decisões e critérios específicos de implementação nos artefatos da feature em `specs/`, sem reescrever os documentos-fonte.
- Adicione uma nova referência a este índice apenas quando ela tiver função distinta e rastreável.

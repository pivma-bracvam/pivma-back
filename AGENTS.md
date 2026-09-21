# Guia para agentes — pi*VMA

## Contexto do repositório

Este repositório contém o backend da pi*VMA. A aplicação usa Python 3.14,
FastAPI, SQLAlchemy assíncrono, Alembic, PostgreSQL com pgvector, Poetry e
Pytest. O código de aplicação fica em `src/pivma/`, as migrações em
`migrations/`, os testes em `tests/` e os artefatos de feature em `specs/`.

Antes de alterar comportamento, leia o código, os testes e a documentação que
tratam da área afetada. Preserve contratos existentes, controles de autorização,
auditoria, isolamento de dados e cegamento quando aplicáveis.

## Fontes de requisitos

Use as fontes nesta ordem:

1. Instruções explícitas do usuário para a tarefa e decisões formais posteriores
   da equipe.
2. [`docs/plano-de-trabalho-fase-ii.md`](docs/plano-de-trabalho-fase-ii.md), a
   conversão em Markdown da documentação oficial de requisitos da Fase II. É a
   principal referência de negócio e registra os requisitos RF001 a RF062.
3. A especificação, o plano e as tarefas aprovados da feature em `specs/`.
4. A constituição em [`.specify/memory/constitution.md`](.specify/memory/constitution.md).
5. O código, as migrações e os testes atuais, que definem o comportamento já
   entregue e os contratos de regressão.

Parte dos requisitos do Plano de Trabalho pode estar desatualizada ou não se
aplicar mais ao produto. Quando uma implementação depender de requisito com
validade, interpretação ou prioridade incerta, registre o conflito e peça o
feedback do usuário antes de implementar. Não preencha essa lacuna com uma
suposição.

Consulte [`docs/guia-prototipo.md`](docs/guia-prototipo.md) para entender a
proposta, telas e fluxos dos vídeos do protótipo. A transcrição pode conter
erros. Use apenas os trechos classificados como `CONFIRMADO NO MATERIAL` como
evidência do material; trate `INFERÊNCIA` e `DÚVIDA / PONTO A VALIDAR` como
itens que exigem validação. O guia não substitui o Plano de Trabalho nem prova
controles de backend.

## Fluxo de trabalho

O Spec Kit está instalado neste repositório. Para features e mudanças de
comportamento relevantes, siga o fluxo local: `speckit-specify` →
`speckit-plan` → `speckit-tasks` → `speckit-implement`. Mantenha a
rastreabilidade entre a fonte de requisito, `spec.md`, `plan.md`, `tasks.md`,
código e testes. Para uma alteração pequena e mecânica, não crie uma spec sem
valor prático.

Defina critérios de aceitação verificáveis antes de implementar. Faça mudanças
cirúrgicas, sem abstrações preventivas, refatorações não relacionadas ou
mudanças fora do escopo. Execute os testes e verificações proporcionais à
alteração e informe somente resultados que foram realmente executados.

## Skills obrigatórias

- Use `andrej-karpathy-skills:karpathy-guidelines` em trabalho de código,
  revisão ou refatoração. Explicite suposições relevantes, prefira a solução
  mais simples e mantenha cada mudança ligada ao pedido.
- Use `stop-slop` somente ao redigir, editar ou revisar texto de documentação,
  como `README.md` e arquivos em `docs/`. Não a aplique ao código.

## Documentação do repositório

Após cada implementação, revise e atualize o [`README.md`](README.md) para
refletir o estado atual do projeto, incluindo instalação, execução, contratos
de API, módulos disponíveis e convenções técnicas quando afetados. Reestruture
ou reduza o README quando isso tornar a documentação mais fácil de consultar,
sem remover informações necessárias.

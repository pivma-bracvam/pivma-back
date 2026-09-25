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

## Testes

- Use `$fastapi-testing-methodology` como regra obrigatória ao planejar,
  especificar, gerar, implementar, revisar ou refatorar testes. Leia o
  `SKILL.md` e consulte suas referências aplicáveis. Ao definir cobertura e
  tarefas de teste, use especialmente a matriz de risco e os critérios de
  parada da metodologia.
- Em features e mudanças de comportamento, inclua no `tasks.md` tarefas de
  teste para os critérios de aceitação e riscos aplicáveis, salvo quando o
  usuário dispensar testes explicitamente. No fluxo Spec Kit, aplique
  `$fastapi-testing-methodology` durante `$speckit-tasks`; a geração de testes
  não depende de um pedido separado de TDD.
- Granularize cada tarefa de teste por um comportamento observável ou critério
  da matriz de risco. Separe sucesso, cada erro/status, limite de autorização,
  isolamento de dados, auditoria, ordenação, paginação e concorrência quando
  forem aplicáveis. Não agrupe resultados distintos em uma única tarefa.
- Organize as tarefas de teste pela história de usuário correspondente e
  coloque-as antes das tarefas de implementação daquela história. Cada tarefa
  deve indicar um resultado verificável e o caminho do arquivo de teste.

## Skills obrigatórias

- Use `$andrej-karpathy-skills:karpathy-guidelines` ao gerar, implementar,
  modificar, revisar ou refatorar código. Durante `$speckit-implement`, aplique
  a skill a cada tarefa de código: explicite suposições e critérios verificáveis,
  escolha a solução mais simples que atende ao pedido e mantenha as mudanças
  cirúrgicas e dentro do escopo. Se uma ambiguidade puder alterar o resultado,
  peça esclarecimento antes de implementar.
- Use `stop-slop` somente ao redigir, editar ou revisar texto de documentação,
  como `README.md` e arquivos em `docs/`. Não a aplique ao código.

## Documentação do repositório

Após cada implementação, revise e atualize o [`README.md`](README.md) para
refletir o estado atual do projeto, incluindo instalação, execução, contratos
de API, módulos disponíveis e convenções técnicas quando afetados. Reestruture
ou reduza o README quando isso tornar a documentação mais fácil de consultar,
sem remover informações necessárias.

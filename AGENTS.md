# Orientações para agentes

## Escopo

Este arquivo se aplica a todo o repositório. Antes de agir, leia o pedido atual, o [README](README.md), o [índice da documentação](docs/README.md) e os arquivos diretamente relacionados à tarefa.

Não presuma que tabelas, endpoints, serviços, modelos, permissões ou fluxos existem. Verifique o código, os testes e a documentação antes de propor ou alterar algo.

## Skills obrigatórias

- Use sempre a skill `andrej-karpathy-skills:karpathy-guidelines` em tarefas de código, revisão, correção, refatoração e planejamento técnico. Faça mudanças pequenas, explícitas e verificáveis.
- Use sempre a skill `stop-slop` ao criar ou revisar relatórios, documentação e outros textos em prosa.
- Quando a tarefa envolver código e texto, use as duas skills: a primeira para delimitar a solução técnica e a segunda para revisar a redação.
- Leia e siga o `SKILL.md` completo da skill aplicável antes de executar a tarefa. A instrução explícita do usuário prevalece se houver conflito.

## Classificação das informações

Ao analisar ou documentar o projeto, identifique a natureza das afirmações:

- **CONFIRMADO:** consta diretamente em fonte oficial, código, teste ou configuração inspecionada. Cite a referência.
- **DECISÃO TÉCNICA REGISTRADA:** define a direção de backend ou infraestrutura e deve orientar a implementação, salvo conflito com o Plano de Trabalho ou decisão formal posterior.
- **INFERÊNCIA:** é uma interpretação apoiada por indícios, mas não declarada pela fonte.
- **PROPOSTA:** é uma decisão futura, recomendação ou direção ainda não especificada e aprovada.

Não transforme inferência ou proposta em fato. Uma decisão técnica registrada pode deixar detalhes para a especificação. Se fontes divergirem, registre a divergência e peça validação quando ela afetar a implementação.

## Fontes e precedência

Use esta ordem para resolver o contexto, sem permitir que uma fonte de menor autoridade altere silenciosamente outra:

1. instrução explícita do usuário para a tarefa atual;
2. Plano de Trabalho oficial e decisões formais da equipe;
3. diretrizes técnicas de backend e infraestrutura registradas em `docs/planejamento/`;
4. especificação da feature aprovada no Spec Kit;
5. código, migrações e testes, como registro do comportamento atualmente implementado;
6. README e configurações operacionais do repositório;
7. vídeos, roteiros e demais materiais do protótipo, como fontes complementares;
8. inferências e propostas, sempre identificadas como tais.

O protótipo não é especificação definitiva. O código existente também não substitui requisitos oficiais: ele confirma apenas o estado atual da implementação.

## Desenvolvimento orientado pelo Spec Kit

O repositório está inicializado com Spec Kit 0.16.2. O desenvolvimento de features e mudanças de comportamento deve ser fundamentado nos artefatos do Spec Kit.

Fluxo padrão:

1. `speckit-specify`: registrar objetivo, requisitos e critérios de aceitação;
2. `speckit-clarify`: resolver lacunas que afetem o comportamento, quando necessário;
3. revisão e aprovação da especificação;
4. `speckit-plan`: definir o plano técnico a partir da especificação e do código real;
5. revisão e aprovação do plano;
6. `speckit-tasks`: gerar tarefas pequenas, ordenadas e rastreáveis. Quando a feature incluir testes, cada tarefa de teste deve cobrir um único comportamento observável (um caminho de sucesso, um código de erro, uma fronteira de autorização, um caso de paginação/concorrência), nunca vários contratos ou variações agregados numa mesma tarefa — leia o Definition of Done da skill `fastapi-testing-methodology` antes de gerar essas tarefas e use seus critérios como unidade de granularidade;
7. `speckit-analyze`: verificar consistência entre especificação, plano e tarefas antes da implementação;
8. `speckit-implement`: executar as tarefas aprovadas;
9. `speckit-converge`: após a implementação, identificar trabalho ainda não atendido, quando aplicável.

Não pule diretamente para a implementação de uma feature sem especificação e critérios verificáveis. Uma correção pequena deve, no mínimo, estar vinculada ao escopo e aos critérios de um artefato existente; não crie uma feature artificial apenas para uma alteração mecânica sem mudança de comportamento.

Os artefatos ficam sob `specs/`, conforme o fluxo instalado em `.specify/`. As skills estão em `.agents/skills/`. A constituição em `.specify/memory/constitution.md` ainda contém somente o template padrão e não deve ser tratada como política ratificada nem preenchida sem uma decisão explícita da equipe.

### Uso proporcional e limite de escopo

O Spec Kit deve receber o peso proporcional ao risco e ao tamanho da mudança:

- **Feature pequena:** `specify` → `clarify` quando necessário → plano curto → tarefas curtas → implementação.
- **Feature sensível ou complexa:** acrescentar checklist, `analyze` e `converge` quando os riscos justificarem essas etapas.

Para qualquer feature, o plano e as tarefas devem obedecer às regras abaixo:

- buscar a menor implementação completa que atenda à especificação aprovada;
- não antecipar funcionalidades futuras, decisões ainda não aprovadas ou arquitetura de outro módulo;
- não criar camadas, abstrações, scripts, dependências ou tarefas de preparação sem uso exigido pela feature atual;
- fazer cada tarefa corresponder a um requisito ou critério de aceitação concreto;
- manter cada tarefa pequena, verificável e ligada aos arquivos necessários;
- separar refatorações não essenciais em outra feature;
- preservar o código e os testes existentes, salvo mudança exigida pela especificação;
- parar e reportar ao usuário se o plano introduzir um aumento relevante de arquivos, dependências, endpoints ou conceitos em relação à spec;
- não iniciar a implementação enquanto esse aumento de escopo não for explicado, reduzido ou aprovado explicitamente.

O `AGENTS.md` orienta o agente, mas não bloqueia tecnicamente o comando do Spec Kit. A verificação prática ocorre na revisão da `spec.md`, do `plan.md` e do `tasks.md` antes da implementação. Se a mesma regra precisar ser aplicada automaticamente à geração, mantenha instruções equivalentes nos templates locais do Spec Kit, sem tratá-los como versionados enquanto `.specify/` permanecer no `.gitignore`.

Ao concluir um artefato do Spec Kit, o agente pode sugerir a próxima etapa com base no tamanho, risco e pendências da tarefa. A sugestão deve explicar o motivo e deixar a decisão de executar `clarify`, `plan`, `tasks`, `analyze`, `implement` ou `converge` com o usuário.

## Estado técnico confirmado

- A aplicação usa Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg e Alembic.
- O banco local é PostgreSQL com a extensão pgvector, executado pelo `compose.yaml`.
- A aplicação é criada em `src/pivma/__init__.py`.
- O exemplo funcional atual inclui `GET /` e `POST /users/`.
- O fluxo de criação de usuário está distribuído entre `src/pivma/routers/users.py`, `src/pivma/schemas.py`, `src/pivma/core/database/models.py` e a migração correspondente.
- Os testes usam Pytest, TestClient, Testcontainers, Factory Boy e PostgreSQL/pgvector descartável fora do Windows.
- `tests/test_app.py`, `tests/routers/test_user.py` e `tests/conftest.py` registram o contrato e a infraestrutura de teste existentes.
- `AuditMixin` mantém campos de criação, atualização e exclusão lógica. Preserve esse padrão ao trabalhar com modelos, salvo decisão diferente registrada na especificação e no plano.

`src/pivma/core/security.py` ainda não implementa autenticação. O cadastro de exemplo não deve ser tratado como implementação de segurança pronta.

## Regras de mudança e teste

- Leia primeiro o teste do comportamento que será alterado.
- Preserve os contratos cobertos pelos testes existentes. Só os altere quando a especificação aprovada exigir uma mudança de comportamento.
- Inclua ou ajuste testes para todo comportamento novo ou corrigido, respeitando a estrutura já usada no repositório.
- Valide autorização no backend. Controles de interface não são suficientes.
- Preserve rastreabilidade, auditoria, isolamento entre laboratórios e cegamento de dados onde o domínio exigir.
- Recursos de IA apoiam a análise; não substituem decisões científicas humanas.
- Não adicione dependências, abstrações ou refatorações fora do escopo sem necessidade demonstrada no plano.
- Não proponha schema, endpoint ou arquitetura de IA antes que o requisito correspondente esteja especificado.
- Execute os testes e verificações proporcionais à mudança. Informe exatamente os comandos executados e seus resultados.
- Nunca declare que testes passaram sem executá-los. O task `poetry test` configura a etapa do Pytest com `ignore_fail = true`; confira a saída do Pytest ou execute `poetry run pytest` diretamente antes de afirmar sucesso.

### Padrão de testes

Ao criar ou alterar testes:

- Siga a skill `fastapi-testing-methodology`. Preserve a separação entre testes unitários, de integração, de API e de segurança, conforme o comportamento e o risco envolvidos.

- Mantenha cada teste focado em um comportamento observável. Use a matriz de risco e o Definition of Done da skill para definir a profundidade da cobertura e os critérios de encerramento.

- Prefira Factory Boy para construir entidades de teste e fixtures Pytest reutilizáveis para preparar estados comuns.

- Para entidades persistidas, prefira preparação por SQLAlchemy ORM (`session.add`, `commit`, `refresh`) em vez de comandos SQL escritos manualmente.

- Para comportamentos expostos pela API, prefira testar o contrato HTTP através do `TestClient`, em vez de chamar diretamente a função do router.

- Chame funções diretamente apenas quando o objetivo for realmente um teste unitário do componente isolado.

- Centralize preparações recorrentes em fixtures ou helpers reutilizáveis, evitando repetir setup de banco, usuários autenticados ou outros estados comuns em vários testes.

- Use `pytest.mark.parametrize` quando vários casos representarem o mesmo comportamento com entradas diferentes.

- Use SQL direto somente quando o nível testado exigir acesso ao schema ou a um estado que o ORM atual não represente adequadamente, especialmente em testes de migração Alembic, constraints específicas do banco ou compatibilidade com schemas anteriores.

- Quando SQL direto for necessário, mantenha-o restrito ao teste de persistência ou migração correspondente e não o use como atalho para preparar dados comuns de testes de API.

- Cada teste deve operar no nível adequado ao comportamento que pretende validar: unidade, API, persistência ou migração.

- Antes de criar nova infraestrutura de testes, verifique as factories, fixtures e helpers existentes e reutilize-os quando forem adequados.

- Evite refatorar a estrutura de testes existente apenas por padronização estética. Faça mudanças estruturais somente quando houver ganho concreto de reutilização, clareza ou manutenção.

## Autenticação planejada

**DECISÃO TÉCNICA REGISTRADA:** a autenticação web usa JWTs transportados por cookies, com `access_token` de curta duração, `refresh_token` persistido para renovação e revogação, e proteção CSRF compatível com esse transporte. Consulte o [backlog técnico de Gestão de Usuários](docs/planejamento/gestao-de-usuarios.md) antes de especificar ou alterar esse fluxo.

As durações, rotação, limites de sessão, atributos definitivos dos cookies, mecanismo CSRF, claims, revogação e logout devem ser especificados e aprovados antes da implementação. Autenticação e autorização devem ser validadas no backend.

## Git e branches

**CONFIRMADO no repositório:** existe a branch local `main` e as referências remotas `origin/main` e `origin/develop`. No momento desta criação, elas apontam para o mesmo commit.

**PROPOSTA informada pela equipe:** desenvolver cada feature de forma incremental em uma branch local própria. Não trabalhe diretamente em `main` ou na branch de integração sem autorização explícita. A equipe mencionou `dev`, mas o remoto atual se chama `develop`; não suponha que os nomes sejam equivalentes sem confirmação.

## Fluxo Git automatizado por solicitação

Pedidos explícitos como `faça o commit`, `faça push`, `abra um PR` ou `publique a feature` autorizam as operações Git e GitHub necessárias para o escopo atual. Não peça confirmação adicional quando os arquivos e o destino estiverem claros.

- Antes de qualquer operação, inspecione `git status`, branch atual, remotos e o diff. Identifique quais arquivos pertencem à tarefa atual.
- Faça staging somente dos arquivos do escopo. Não use `git add .`, `git add -A` nem inclua alterações preexistentes ou de outra autoria.
- Se o diff misturar alterações sem relação com a tarefa, pare e peça que o usuário delimite os arquivos. Não descarte, reverta ou mova essas alterações por conta própria.
- Antes do commit, execute as verificações proporcionais à mudança e registre o resultado. Se uma verificação falhar, relate a falha e não faça o commit, salvo instrução explícita para registrá-lo mesmo assim.
- Crie commits pequenos, com mensagem concisa e fiel ao conteúdo. Não faça commits automáticos ao final de uma tarefa sem pedido explícito do usuário.
- Um pedido para abrir PR inclui, quando necessário, criar ou selecionar uma branch de feature, fazer staging seletivo, criar o commit, enviar a branch ao remoto e abrir o PR.
- Para abrir PR, use a skill `gh-create-pr`. Inspecione a base, o diff e os metadados disponíveis antes da criação; registre no corpo o escopo e os testes executados.
- A convenção inicial para PRs de feature é usar `develop` como base, pois essa é a branch de integração existente no remoto. Use outra base somente quando o usuário, a feature ou uma convenção posterior indicar.
- Crie branch com nome curto e descritivo, usando prefixo compatível com o escopo, como `feat/`, `fix/`, `docs/`, `test/` ou `chore/`.
- Em PRs, aplique apenas labels, milestone e projeto que já existam e tenham relação clara com a mudança. Atribua o PR a `brugabi` quando a plataforma permitir.
- Após commit, push ou PR, informe hash ou URL, branches de origem e destino, arquivos incluídos, testes executados e qualquer item que não tenha sido aplicado.

## Documentação

O mapa de fontes e os caminhos de leitura estão em [docs/README.md](docs/README.md). Ao atualizar a documentação:

- preserve a terminologia e a redação dos requisitos oficiais;
- não corrija ambiguidades silenciosamente;
- mantenha requisitos, códigos e rastreabilidade até a fonte;
- registre divergências e lacunas em `docs/observacoes-e-pendencias.md`;
- mantenha fatos do protótipo separados de inferências e dúvidas;
- não crie ADRs antes de uma decisão arquitetural aprovada;
- evite fragmentar a documentação sem uma necessidade concreta.

## Critério de conclusão

Uma tarefa só está concluída quando o escopo solicitado foi atendido, as referências relevantes foram atualizadas, os testes aplicáveis foram executados e o resultado foi relatado sem ocultar falhas, limitações ou pendências.

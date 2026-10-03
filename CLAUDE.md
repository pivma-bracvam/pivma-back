# Instruções do projeto

@AGENTS.md

Antes de qualquer tarefa neste repositório, consulte e siga integralmente as diretrizes normativas do projeto, em `AGENTS.md` (importado acima) e na constituição `.specify/memory/constitution.md`. Elas definem o escopo, as skills obrigatórias, a precedência de fontes, o fluxo do Spec Kit, o estado técnico confirmado, as regras de teste, a autenticação planejada, o fluxo de git/branches e os critérios de conclusão.

Não resuma nem substitua as diretrizes normativas por este arquivo: consulte a documentação oficial sempre que for atualizada, pois as regras de referência não são copiadas nem versionadas aqui.

## Equivalência de skills obrigatórias para Claude Code

As diretrizes do projeto determinam skills obrigatórias assumindo o carregamento automático usado por outros agentes. Para Claude Code, mencionar o nome da skill no texto de instrução **não** a carrega: é preciso chamar a ferramenta `Skill` explicitamente com esse nome antes de iniciar a tarefa. Sempre que houver a indicação "use a skill X", trate isso como "chame `Skill({skill: "X"})` antes de agir", não como uma referência passiva.

Equivalências confirmadas neste ambiente:

- `karpathy-guidelines` (exigida em toda tarefa de código, revisão, correção, refatoração e planejamento técnico) → versionada em `.agents/skills/` e disponível via `.claude/skills` (symlink). Chame `Skill({skill: "karpathy-guidelines"})` no início dessas tarefas. Quem tiver o plugin global `andrej-karpathy-skills` pode usar `andrej-karpathy-skills:karpathy-guidelines`, que tem o mesmo conteúdo.
- `testing-methodology` (exigida ao criar ou alterar testes) → disponível via `.claude/skills` (symlink para `.agents/skills/`). Chame `Skill({skill: "testing-methodology"})` antes de escrever ou alterar testes.
- `speckit-*` (fluxo do Spec Kit) → disponíveis para Claude Code com os mesmos nomes via `.claude/skills`; normalmente acionadas pelo usuário via `/speckit-*`, mas Claude também pode chamá-las diretamente pela ferramenta `Skill` quando o fluxo exigir.
- `stop-slop` (exigida ao criar ou revisar relatórios, documentação e textos em prosa) → versionada em `.agents/skills/` e disponível via `.claude/skills` (symlink). Chame `Skill({skill: "stop-slop"})` antes de escrever ou revisar prosa.
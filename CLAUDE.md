# Instruções do projeto

Antes de qualquer tarefa neste repositório, leia e siga integralmente o [AGENTS.md](AGENTS.md). Ele é a fonte normativa de escopo, skills obrigatórias, precedência de fontes, fluxo do Spec Kit, estado técnico confirmado, regras de teste, autenticação planejada, git/branches e critério de conclusão.

Não resuma nem substitua o `AGENTS.md` por este arquivo: releia o original sempre que ele for atualizado, pois esta referência não é copiada nem versionada aqui.

## Equivalência de skills obrigatórias para Claude Code

O AGENTS.md nomeia skills obrigatórias assumindo o carregamento automático usado por outros agentes. Para Claude Code, mencionar o nome da skill no texto de instrução **não** a carrega: é preciso chamar a ferramenta `Skill` explicitamente com esse nome antes de iniciar a tarefa. Sempre que o AGENTS.md disser "use a skill X", trate isso como "chame `Skill({skill: "X"})` antes de agir", não como uma referência passiva.

Equivalências confirmadas neste ambiente:

- `andrej-karpathy-skills:karpathy-guidelines` (exigida em toda tarefa de código, revisão, correção, refatoração e planejamento técnico) → plugin global disponível para Claude Code com esse mesmo nome. Chame `Skill({skill: "andrej-karpathy-skills:karpathy-guidelines"})` no início dessas tarefas.
- `fastapi-testing-methodology` (exigida ao criar ou alterar testes) → disponível para Claude Code com esse mesmo nome via `.claude/skills` (symlink para `.agents/skills/`). Chame `Skill({skill: "fastapi-testing-methodology"})` antes de escrever ou alterar testes.
- `speckit-*` (fluxo do Spec Kit) → disponíveis para Claude Code com os mesmos nomes via `.claude/skills`; normalmente acionadas pelo usuário via `/speckit-*`, mas Claude também pode chamá-las diretamente pela ferramenta `Skill` quando o fluxo exigir.
- `stop-slop` (exigida ao criar ou revisar relatórios, documentação e textos em prosa) → **sem equivalente instalado para Claude Code neste ambiente.** Não existe plugin nem skill local com esse nome. Até que seja instalada, informe essa lacuna quando a tarefa envolver texto em prosa relevante, em vez de presumir cumprimento.

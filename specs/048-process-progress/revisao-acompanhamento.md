# Revisão da Spec 048: acompanhamento do processo

**Data**: 2026-11-27

**PR**: #83 (`feat/047-sponsor-tracking`, commit `abe9eed`), comparado com a `develop` no commit `2f1d4a0`

Este documento detalha o comentário de revisão do PR #83. Ele registra o que a proposta atual não cobre, por que isso importa e que desenho evita os mesmos problemas nas próximas telas.

## Motivação

O front precisa de uma tela de acompanhamento para vários cargos: Patrocinador, proponente, laboratórios, revisores, colaboradores e observadores. Cada cargo vê um recorte diferente, e as regras de sigilo em vigor limitam esse recorte: isolamento por laboratório (RF044), revisão cega (RF050) e autoria oculta da triagem (Spec 046).

A equipe preparou, a partir do OECD Series on Testing and Assessment No. 34 (GD34), uma análise das questões de acesso que ainda dependem do BraCVAM: o papel do Colaborador, a identidade do proponente perante os laboratórios, quem vê o nome de quem, o que o Patrocinador acompanha na Fase 3, entre outras. A GD34 orienta sobre independência dos laboratórios, codificação das amostras e revisão independente, mas não define as permissões da pi\*VMA. As respostas virão do BraCVAM e vão mudar a tabela de quem vê o quê.

Por isso a revisão olha menos para o recorte de hoje e mais para uma pergunta: **quando o BraCVAM mudar uma regra, quantos lugares do código precisam mudar?**

## As duas propostas

A ideia inicial era ampliar `GET /tasks` para ser a única fonte de leitura do que acontece no processo. A caixa de trabalho, o kanban e o acompanhamento leriam a mesma rota com filtros diferentes. O PR #83 propõe outra rota: `GET /processes/{id}/progress`, mais três campos em cada item de `GET /processes`.

Os problemas que o acompanhamento precisa resolver, e o que cada proposta cobre:

| Problema | `/tasks` ampliado | `/progress` (PR #83) |
|---|---|---|
| Ver o que terminou e o que está em andamento nos outros cargos | Sim, por atividade, com prazo | Em parte: atividades em andamento e situação da fase |
| Ver os próximos passos dentro da fase (RF030: pendentes e futuras) | Sim, com custo no contrato da tarefa | Não |
| Uma regra de visibilidade igual em todas as rotas | Sim para atividades | Não: cria uma regra nova |
| Não criar uma rota por tela | Sim | Uma rota nova |
| Quem ocupa cada cargo (o "Não atribuído" do front) | Não | Sim |
| Cartão da lista com a fase, numa chamada | Não | Sim |
| Fase atual igual para todos os cargos | Não: cada cargo calcula com o que vê | Sim |

Cada proposta resolve metade. A melhor saída junta as duas:
- o `/progress` fica com o que é do processo: fases, pessoas e cartão;
- uma regra única, declarada como dado, decide o que cada cargo vê, e o `/progress`, o `/tasks` e a linha do tempo leem essa mesma regra.

## Achados

### 1. Quatro regras de visibilidade, e elas já divergem

Hoje quatro lugares decidem, cada um à sua maneira, o que um cargo vê:

| Onde | Regra |
|---|---|
| `GET /tasks` | `activity_view_clause` (`view_roles` do template) e `laboratory_run_visibility_clause` (`src/pivma/core/authorization.py:522`) |
| Linha do tempo | `_visible_events` (`src/pivma/routers/processes.py:219`), com filtros próprios de atividade, laboratório e participante |
| `GET /processes/{id}/participants` | `participant_read_scope` (`src/pivma/core/authorization.py:667`): quem não gere participantes vê só a própria designação |
| `GET /processes/{id}/progress` | `ProgressView` (`src/pivma/core/process_progress.py:69`), com grupos fixos de cargos |

As regras já dão respostas diferentes para a mesma pessoa e o mesmo processo:

- **O Patrocinador** vê as execuções de todos os laboratórios no andamento (`FULL_VIEW_ROLES`, `process_progress.py:57`). No `/tasks` ele não vê nenhuma, porque `laboratory_run_visibility_clause` só abre exceção para o `group_manager`. Nos cinco templates, todas as atividades têm `view: []`, então o Patrocinador recebe um `/tasks` vazio.
- **As atividades em andamento** do `/progress` ignoram `view_roles`. `open_runs` (`process_progress.py:163`) filtra só por laboratório. Um avaliador vê, por exemplo, que a revisão do retorno da submissão está aberta, e o `/tasks` esconderia essa atividade dele.
- **A linha do tempo** expõe convites e autores que o andamento esconde. A issue #84 registra o vazamento e propõe reaproveitar a regra de cegamento do `ProgressView`, ou seja, copiar a regra para um quinto lugar.

Cada regra nova é mais um lugar que alguém precisa manter alinhado quando o BraCVAM responder.

### 2. Regras fixas no código

`FULL_VIEW_ROLES`, `COORDINATION_ROLES` e `BLIND_REVIEW_ROLES` (`process_progress.py:57-65`) são constantes. Mudar o que um cargo acompanha, ou incluir um cargo novo, pede alteração de código, revisão e deploy. O template já guarda as concessões de editar e ver por atividade (`access.edit` e `access.view`), e o acompanhamento não usa esse lugar.

### 3. Os próximos passos não aparecem

A resposta traz as fases com a situação e as atividades em andamento. Uma atividade bloqueada, que ainda depende de outras, não aparece. O RF030 pede as etapas concluídas, em andamento, pendentes e futuras. Dentro de uma fase, o usuário vê o que está aberto e não vê o que vem depois.

As atividades condicionais precisam de marca própria. A revisão do retorno e a resolução de problemas no recebimento só abrem se algo acontecer (`EVENT_OPENED_ACTIVITY_TYPES`, `src/pivma/core/process_engine.py:150`). Na lista, elas não podem parecer etapas certas.

### 4. O detalhe por cargo vai chegar

Com a execução nos laboratórios (RF041 a RF045), o monitoramento interlaboratorial (RF046) e a revisão por pares (RF048 a RF054), cada cargo vai querer abrir uma etapa e ver um resumo do que aconteceu nela. O laboratório, por exemplo, quer saber que o próprio lote chegou com "4 frascos em ordem, 1 reenviado".

O recebimento de amostras já mostra o problema. O mesmo frasco sai em duas versões: o laboratório recebe código, lote e orientação, sem identidade química (`_serialize_vials`, `src/pivma/core/sample_receipt_service.py:317`); o Grupo de Seleção recebe também nome químico, CAS e justificativa (`_serialize_nonconformities`, linha 773). Um resumo para quem só acompanha seria uma terceira versão.

### 5. Correções pontuais

- `open_runs` não filtra `deleted_at` de `ActivityRun` nem de `ActivityInstance`, e a consulta de fases em `build_progress` (`process_progress.py:229`) não filtra `Phase`. Execuções e fases excluídas entram na contagem, na lista e na fase atual.
- A descrição do PR diz que os alerts usam a regra do `/tasks`. Os alerts escolhem os destinatários por `can_act` (`alert_task_opened`, `src/pivma/core/alert_service.py:169`), que parte de `edit_roles`. Mudar quem vê uma tarefa não muda quem recebe o alerta. O argumento não sustenta a escolha entre as propostas.
- Quando um cargo vê o cargo mas não o nome de quem o ocupa, o contrato precisa dizer se o cargo está ocupado sem listar as pessoas. Uma lista de pessoas sem nome vira uma contagem, e com dois ou três laboratórios uma contagem identifica quem é quem.
- O acúmulo de cargos fica com a issue #85, que limita a pessoa a um cargo ativo por processo. O `ProgressView` não precisa de regra de precedência entre cargos. O teste `test_avaliador_com_outro_cargo_ve_a_uniao` (`tests/api/routers/test_process_progress_visibility.py:199`) cobre exatamente o caso que a #85 proíbe.

## Proposta: uma matriz de acesso central

### O que é

Um conjunto de regras declaradas como dado, num lugar só, com três partes:

1. **Por atividade**, no template, ao lado do `access` que já existe: quem acompanha a situação, quem vê o resumo, quem vê o conteúdo e quem edita. Nas atividades por laboratório, cada concessão tem escopo: o próprio laboratório ou todos.
2. **Identidade**, num arquivo central: de quais cargos cada cargo vê o nome.
3. **Restrições por cargo**, no mesmo arquivo: as regras de sigilo que acompanham o cargo, como o isolamento por laboratório e a revisão cega.

Exemplo de formato. Os valores ficam a definir com o BraCVAM.

```yaml
# template: atividade por atividade
- key: sample_receipt
  execution_scope: per_laboratory
  access:
    edit:    [{role: participating_laboratory, scope: own}]
    view:    [{role: participating_laboratory, scope: own}]
    summary: []   # a definir
    track:   []   # a definir

# arquivo central
identity:
  sponsor: { names_of: [] }        # a definir
restrictions:
  participating_laboratory: [own_laboratory_only]
  adhoc_evaluator: [blind_review]
  peer_reviewer: [blind_review]
```

Na primeira versão, os valores reproduzem o comportamento atual do PR. A resposta do BraCVAM entra depois como alteração da matriz.

### Como funciona

- **Uma função de verificação.** Todas as leituras chamam a mesma função: `/progress`, `/tasks`, a linha do tempo e `/participants`. Nenhuma rota decide visibilidade por conta própria. Para as listagens, a função tem também uma versão em SQL, como já acontece com `is_process_manager` e `laboratory_run_visibility_clause`.
- **Negação por padrão.** Cargo, atividade ou campo fora da matriz não aparece.
- **Os níveis não se misturam.** Acompanhar a situação não libera o resumo, e o resumo não libera o conteúdo. As rotas de formulário, amostras e recebimento continuam exigindo `view`.
- **O resumo vem de uma lista de campos permitidos.** Cada tipo de atividade monta o próprio resumo campo a campo. Montar o resumo apagando campos do objeto completo vaza o próximo campo que alguém acrescentar.
- **Os alerts ficam fora.** Os destinatários continuam saindo de `edit_roles`, por `can_act`. Quem só acompanha não passa a receber alertas.

### Por que isso resolve

| Problema | Como a matriz resolve |
|---|---|
| Quatro regras divergentes | Uma função, chamada por todas as rotas |
| Regras fixas no código | Mudar quem vê o quê é editar a matriz |
| Linha do tempo vazando (#84) | A linha do tempo passa a usar a mesma função |
| Detalhe por cargo no futuro | O nível de resumo já existe na matriz |
| Alinhamento com o BraCVAM | A matriz vira o documento das perguntas |

### A matriz como documento para o BraCVAM

Uma página do manual gerada a partir da matriz mostra a tabela de quem vê o quê, atividade por atividade e cargo por cargo. As perguntas ao BraCVAM saem dessa tabela. A resposta vira uma alteração na matriz, revisada como qualquer mudança de código, e a página se atualiza junto.

### Testes gerados da matriz

Cada célula da matriz vira um caso de teste: cargo, atividade, nível e resultado esperado. O teste chama as rotas de verdade. Se uma rota se afastar da regra, o teste falha. Se alguém mudar a matriz, o resultado esperado muda junto, e a revisão mostra a diferença.

Os testes também cobrem a versão em SQL e a versão em Python da função, para que as duas não divirjam.

### Decisão de desenho antes de implementar

Hoje a criação do processo copia as concessões do template para cada atividade (`act.view_roles, act.edit_roles = resolve_activity_access(a_data)`, `src/pivma/core/process_engine.py:761`). Com isso, mudar a matriz só afeta processos novos. Há duas saídas:

- **Resolver pela versão do template na leitura.** A regra nova vale para todos os processos daquela versão. É mais simples de manter, mas a mudança de regra alcança processos em andamento sem migração.
- **Manter a cópia e migrar.** Cada mudança de regra exige uma migração de dados para os processos em andamento. É mais trabalhoso, mas deixa registrado o que valia para cada processo.

A escolha depende de quanto a equipe quer que uma resposta do BraCVAM valha para os processos já abertos.

## O que fazer neste PR e depois

**Neste PR**
- Criar a matriz com as partes que o andamento usa: acompanhar a situação, por atividade, e identidade, por cargo. Os valores iniciais reproduzem o comportamento atual.
- Fazer o `/progress` e o `/tasks` lerem a mesma função. O `/tasks` continua sendo a caixa de trabalho: o acompanhamento entra lá só com um parâmetro explícito, sem mudar a resposta padrão.
- Listar as atividades de cada fase com a situação e a marca de condicional.
- Gerar os testes a partir da matriz.
- Aplicar as correções pontuais.

**Depois**
- Linha do tempo (#84) e `/participants` passam a usar a mesma função.
- Nível de resumo por tipo de atividade, quando a execução nos laboratórios e a revisão por pares existirem.
- Página do manual gerada a partir da matriz.

## Fontes

- **Plano de Trabalho da Fase II** (`docs/plano-de-trabalho-fase-ii.md`): RF030 (visualização do fluxo), RF044 (controle de acesso por laboratório), RF046 (monitoramento interlaboratorial), RF050 (revisão cega).
- **OECD Series on Testing and Assessment No. 34** (GD34, 2005): base da análise das questões de acesso preparada pela equipe para o BraCVAM.
- **Specs**: 030 (acesso por atividade), 032 (listagem de tarefas e `can_act`), 036 e 037 (execução e isolamento por laboratório), 040 (recebimento de amostras), 046 (autoria oculta da triagem), 047 (alerts).
- **Issues**: #84 (linha do tempo expõe convites e autores), #85 (acúmulo de cargos), #86 (`can_act` de execução de laboratório ignora `edit_roles`).
- **Código**: `develop` em `2f1d4a0` e esta branch em `abe9eed`, nos arquivos citados ao longo do texto.

# Phase 0 — Research: Pacote de Baseline do Primeiro Deploy

## R1 — Agrupamento por seções do FP usando apenas YAML

**Decision**: Declarar cada seção do FP com `validation_rules: { section: "<nome>" }`
no campo, no YAML de `05_proof_of_concept.yaml`.

**Rationale**: `bootstrap_process_templates._sync_form_fields` copia `validation_rules`
literalmente para a coluna JSONB e **não** processa uma chave `section` de primeiro
nível. O endpoint `GET /processes/{id}/activities/{activity_key}/form`
(`routers/forms.py`) expõe a seção lendo `f.validation_rules.get('section')`. Portanto,
a seção só chega à interface quando está dentro de `validation_rules`. O `README.md`
de `templates_data` (seção 5.3) já documenta essa forma como válida.

**Alternatives considered**:
- `section` como chave de primeiro nível do campo (como no editor via
  `update_form_template_definition`): rejeitado — o caminho de bootstrap YAML não lê
  essa chave; só o editor a converte.
- Adicionar coluna `section` a `FormField` + migração: rejeitado — fora de escopo
  (Constituição: sem mudança de schema para esta feature; sem necessidade real).

## R2 — Qual processo carrega a pré-avaliação por IA nas demos

**Decision**: A pré-avaliação por IA passa a viver no **processo 4**
(`validated_method_dossier` / formulário `submission_validated_dossier_v1`). O
`seed_ai_evaluations` publica a definição de avaliação, associa-a a um campo de IA do
formulário 4 e avança a instância oficial `[DEMO 4] …` (criada por `seed_forms`) por
submissão → pré-avaliação → triagem. Não há mais um processo `[DEMO IA]` separado.

**Rationale**:
- A spec (User Story 3) define o processo 4 como o que "exemplifica o uso da IA"; os
  processos 1‑3 ficam com um único campo, sem IA.
- As demos de **triagem** e de **observabilidade de IA** precisam de um processo em
  triagem com pré-avaliação executada (`get_pre_evaluation`, `/admin/logs/ai`). O
  gatilho é a existência de `EvaluationAssignment` habilitada para o `form_template`
  submetido (`submit_proposal_form`). Colocar a atribuição no formulário 4 satisfaz
  ambas as demos com uma única instância.
- Hoje `seed_ai_evaluations` cria `[DEMO IA] Extensão de Escopo …`, cujo título não
  está em `OFFICIAL_DEMO_PROCESSES`; `seed_forms` e `seed_triage` fazem
  `UPDATE … SET deleted_at = now() WHERE title NOT IN (valid_titles)`. Reaproveitar a
  instância oficial `[DEMO 4]` elimina essa fragilidade de ordem de execução.

**Alternatives considered**:
- Adicionar `[DEMO IA] …` à lista `OFFICIAL_DEMO_PROCESSES`: resolveria o soft-delete,
  mas mantém dois processos para a mesma história e mais massa que o necessário.
- Manter a IA no formulário 2 (`scope_extension`): conflita diretamente com a decisão
  de clarificação (formulários 1‑3 = um campo).
- Manter um campo de IA no formulário 1: viola a restrição "exatamente um campo".

## R3 — Mapeamento do Formulário Preliminar (FP) para tipos suportados

**Decision**: Converter o FP para um único formulário de submissão
(`submission_proof_of_concept_v1`) com todos os campos agrupados nas 9 seções do
documento, aplicando a regra de aproximação da clarificação:

| Elemento do FP | Aproximação no sistema | Pendência |
| :-- | :-- | :-- |
| Blocos de contato (proponente, contato adicional, endereço se diferente) | Vários campos `text`/`select` (titulação → `select`) agrupados por `section` | "Contato adicional" e "endereço se diferente" ficam como campos sempre visíveis; não há repetição de bloco |
| 3.1 "aborda: saúde humana / ambiental / outros" (múltipla escolha + especificar) | 3 campos `boolean` + 3 `textarea` "especifique" sempre visíveis | Sem grupo de checkbox; sem visibilidade condicional |
| 3.2–3.10 (textos ≤150 palavras) | `textarea` com `help_text` indicando o limite | Limite por palavras não é validado (só `min_length` em caracteres) |
| 4.1–4.6, 5.1–5.3, 6.1–6.6 (SIM/NÃO + descrição) | Par de campos por item: `boolean` (SIM/NÃO) + `textarea` (descrição) | "Se sim, especifique" sempre visível |
| 4.2 controles (positivo/negativo/referência) | 3 pares `boolean` + `textarea` | Sem grupo de checkbox |
| 7. Referências (lista de até 10) | 1 `textarea` (uma referência por linha) | Sem lista repetível estruturada |
| 8. Declaração de confidencialidade (tabela de até 20 linhas: item + explicação) | 1 `boolean` ("contém informação confidencial?") + 1 `textarea` (itens e justificativas) | Sem tabela/grupo repetível; sem vínculo parágrafo↔marcação |
| 4.1 anexar POPs / documento de projeto | `file_upload` com `allowed_extensions: [pdf]` | — |
| 9. Solicitação ao BraCVAM (SIM/NÃO + especificar) | `boolean` + `textarea` | — |

Toda linha marcada como pendência acima é repetida na seção "Pendências e Lacunas
Conhecidas" do `spec.md` (já presente) e detalhada em `data-model.md`.

**Rationale**: mantém as 9 seções visíveis (fidelidade estrutural), nunca omite um
elemento, e usa só tipos suportados. `boolean` + `textarea` é a forma mais fiel de
representar "SIM/NÃO + descrição" recorrente no FP.

**Alternatives considered**:
- `select` de 2 opções em vez de `boolean` para SIM/NÃO: equivalente; `boolean`
  (switch/checkbox) é mais direto e já é o componente sugerido no README.
- Colapsar seções 7 e 8 em uma nota única (opção C da clarificação): rejeitada pelo
  usuário (resposta A — aproximar cada elemento).

## R4 — Remediação do acoplamento dos testes à forma antiga dos formulários

**Decision**: Re-apontar o helper central `tests/ai_eval_helpers.py` para o formulário
4: `SUBMISSION_TEMPLATE = 'submission_validated_dossier_v1'`, `AI_FIELD =
'<campo de IA do form 4>'`, `create_and_submit_process` usando
`template_key='validated_method_dossier'`, e `FULL_VALUES` com os campos do formulário
4. Ajustar pontualmente os testes que declaram suas próprias constantes
(`test_evaluation_assignments.py`, `test_evaluation_library.py`,
`test_evaluation_library_reuse.py`) e a massa de rascunho/submissão em
`test_process_engine.py` (que usa `endpoint_target` e `scientific_justification`).

**Rationale**: 15 arquivos de teste consomem `ai_eval_helpers`; centralizar a mudança
no helper resolve a maioria com um diff pequeno. `submit_proposal_form` ignora chaves
desconhecidas e só valida obrigatórios, então testes que enviam campos extras
continuam passando sem edição. O que quebra de fato é: (a) salvar rascunho com chave
removida (`_validate_draft_values` levanta `unknown_field`), (b) criar
`EvaluationAssignment` para um `field_key` inexistente, (c) asserts sobre campos de IA
específicos.

**Alternatives considered**:
- Criar um `ProcessTemplate`/formulário exclusivo de teste (fixture/factory) e
  desacoplar os testes de IA dos YAML de demo: solução mais limpa e alinhada à
  Constituição IV (factories em vez de dados de seed), porém maior; registrada como
  dívida técnica recomendada para uma feature futura.
- Manter um campo de IA "genérico" em um dos formulários 1‑3: viola a restrição de
  "exatamente um campo".

## R5 — `FormField` órfão em re-seed e limites por número de palavras

**Decision**:
- `quickstart.md` assume **banco migrado e vazio** para a validação da carga; é o
  cenário de "primeiro deploy". A idempotência exigida (SC‑003) refere-se a
  usuários/processos/avaliações, garantida pelos guards `get_or_create`/`exists` dos
  seeds.
- **Item opcional de robustez (P3)**: em `_sync_form_fields`, após o upsert, soft-delete
  (`deleted_at`) dos `FormField` do formulário cujo `field_key` não está mais no YAML,
  **apenas** quando não houver `FormValue` ativo referenciando o campo; caso contrário,
  manter e registrar em log. Coberto por teste dedicado de bootstrap (estado antes/depois).
- Limites "máx. N palavras" do FP: **não** aplicados; orientação só via `help_text`.
  `validation_rules` suporta `min`/`max` (numérico) e `min_length` (caracteres), não
  contagem de palavras nem `max_length`.

**Rationale**: manter o escopo em dados/scripts/páginas. A poda é a única melhoria de
domínio cogitada e é conservadora (soft-delete, guardada por ausência de valores). No
primeiro deploy o banco está limpo, então a poda não altera o resultado — é rede de
segurança para re-seeds em ambiente de demonstração.

**Alternatives considered**:
- Poda incondicional de campos ausentes: rejeitada — poderia esconder dados históricos
  (Constituição V).
- Validação de contagem de palavras no motor: rejeitada — mudança de motor fora de
  escopo (spec, "Out of Scope").

## R6 — Comando de carga canônico e padrão visual das demos

**Decision**:
- Comando único citado em todas as páginas e no catálogo:
  `uv run python -m scripts.seeds.seed_all`. Remover as variações
  `poetry run python scripts/seeds/seed_all.py` e `scripts/seeds/seed_all.py`.
- Padrão visual compartilhado extraído para `demos/assets/base.css` (tokens de cor,
  tipografia, cabeçalho, cartões, botões) e, opcionalmente, `demos/assets/base.js`
  (componente de status da API — hoje duplicado em cada página). Cada uma das 6 páginas
  passa a importar esses assets e é reescrita para o mesmo esqueleto: cabeçalho com
  título curto + status da API → 1 frase do que a demo mostra → passos numerados
  curtos → chamada de ação. Textos em português; termo em inglês só sem equivalente
  corrente.
- `demos/index.html` lista as 6 páginas (4 do ciclo + 2 de apoio) com uma descrição de
  uma linha cada e sem link para `DESIGN.md`.
- Diretriz de padrão registrada em `demos/README.md` curto (substitui o `DESIGN.md`
  removido, sem recriá-lo).

**Rationale**: `base.css`/`base.js` vivem dentro de `demos/`, sem qualquer import de
`src/` — mantêm o desacoplamento (Constituição II) e a descartabilidade. Um esqueleto
único é o que torna o checklist de "padrão consistente" (SC‑004) verificável.

**Alternatives considered**:
- Framework/CSS externo (Tailwind, etc.): rejeitado — dependência nova para páginas
  descartáveis; CSS simples basta.
- Manter estilos por página só com uma folha comum importada: cobre cor/tipografia mas
  não a estrutura/tom; a clarificação pediu reescrita das 6 páginas.
- Recriar `DESIGN.md`: proibido pela spec.

## Skills obrigatórias — estado neste ambiente

- `fastapi-testing-methodology`: **disponível**. Chamar antes de criar/alterar testes.
- `andrej-karpathy-skills:karpathy-guidelines`: **não instalada** (nem plugin global
  nem skill local). Lacuna declarada no `plan.md` e no `spec.md`; princípios aplicados
  manualmente.
- `stop-slop`: **não instalada**. Lacuna declarada; textos de `README`/`demo-standard`
  mantidos curtos e factuais.

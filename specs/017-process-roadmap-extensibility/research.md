# Research: Roteiro Dinâmico e Extensibilidade de Atividades

**Feature**: 017-process-roadmap-extensibility
**Date**: 2026-09-11

Nenhum `NEEDS CLARIFICATION` restou no Technical Context — as decisões abaixo já haviam
sido levantadas e fechadas na conversa que originou a spec. Este documento apenas as
consolida no formato Decision/Rationale/Alternatives.

---

## 1. Onde armazenar a classificação da atividade

**Decision**: nova coluna `activity_type` (`VARCHAR(32)`, `NOT NULL`, `default='form'`)
em `activity_instances`, populada a partir do campo opcional `activity_type` do YAML de
cada atividade (default `form` quando ausente).

**Rationale**: `ActivityInstance` (Spec 004) já é a entidade que representa "uma unidade
de trabalho declarada no processo" — adicionar o atributo ali evita criar uma tabela ou
abstração paralela (proibido pela Constituição, Princípio II, e pela própria Spec 004).
Default `form` preserva 100% do comportamento e dos dados existentes sem migração de
conteúdo.

**Alternatives considered**:
- Uma tabela `activity_type` normalizada (catálogo): rejeitada por excesso de
  engenharia para um conjunto fechado e pequeno de valores (FR-004 da spec).
- Inferir o tipo pela presença/ausência de `form_template_key`: rejeitada por ser
  implícito — não permite distinguir "decisão" de "tarefa externa" de "marcador", que a
  spec exige como classificações distintas (FR-004).

---

## 2. Onde publicar a Fase 2 de exemplo

**Decision**: nova versão (`version: 2`) do template `validated_method_dossier`
(`04_validated_method_dossier.yaml`, Spec 011), reaproveitando-o como veículo de
validação — mesmo padrão já usado pela Spec 013 para o pipeline de IA nesse método.

**Rationale**: decisão explícita do usuário (ver spec.md, "Decisão registrada nesta
revisão"), priorizando testar a extensão dentro do caminho real que um proponente
percorre, em vez de um template isolado sem tráfego real algum.

**Alternatives considered**:
- Template de demonstração isolado e inativo (a primeira redação desta spec):
  rejeitado pelo usuário — validado com API real, mas sem exercitar o método oficial que
  vai de fato precisar da Fase 2 futuramente.

**Risco aceito e mitigação**: instâncias criadas a partir da nova versão (2) passam a
exibir a Fase 2 de exemplo; instâncias já existentes, criadas sob a versão 1, **não são
afetadas** — a Spec 004 já garante (FR-001/SC-002) que uma instância permanece vinculada
à versão exata do template no momento em que foi criada. Publicar como nova versão (em
vez de editar a versão 1 in-place) é o que torna essa garantia válida aqui; o loader atual
(`_sync_process_template_and_version`) só cria uma versão nova quando o número de versão
do YAML muda — por isso o bump para `version: 2` é obrigatório, não incidental.

---

## 3. Como desbloquear a atividade da Fase 2 quando a Fase 1 é aprovada

**Decision**: generalizar minimamente o desbloqueio de atividade dependente. Hoje
`_handle_approved_decision` apenas marca a fase 1 como `COMPLETED` e o processo como
`PLANNING`, sem avaliar `ActivityDependency`. Esta spec adiciona um passo, após marcar a
triagem concluída, que busca atividades `BLOCKED` cuja dependência aponte para a
atividade recém-concluída e, quando todas as dependências dela estiverem satisfeitas,
ativa a atividade (mesmo efeito hoje restrito a `_unblock_triage_activity`, mas dirigido
pelas linhas de `ActivityDependency` já gravadas na instanciação, em vez de uma chave de
atividade hardcoded).

**Rationale**: a Spec 004 já modela `ActivityDependency` com essa finalidade (FR-007);
hoje ela é gravada mas nunca lida de volta para decidir avanço — esta spec fecha esse
ciclo no caso mínimo necessário (uma dependência simples, `ACTIVITY_COMPLETED`), sem
construir um motor de regras genérico completo (fora de escopo, ver spec.md "Out of
Scope").

**Alternatives considered**:
- Hardcodear o desbloqueio da nova atividade por chave, como já existe para
  `triage_evaluation`: rejeitada por repetir exatamente o padrão que a Spec 017 existe
  para eliminar (cada fase nova não pode exigir uma função dedicada no motor).

---

## 4. Como o frontend/demo enxerga o roteiro sem uma nova consulta agregada

**Decision**: para esta validação, a demo compõe o roteiro no cliente combinando três
chamadas já existentes: `GET /processes/templates/{key}` (estrutura declarada, incluindo
a Fase 2 e seu `activity_type`), `GET /processes/{id}` (status macro) e
`GET /tasks?process_id={id}` (status por atividade, já que cada atividade — inclusive a
de exemplo — continua produzindo exatamente uma `Task`, mesma convenção da Fase 1).

**Rationale**: a User Story 1 da Spec 017 (uma consulta agregada dedicada ao roteiro)
continua válida como evolução futura, mas não é pré-requisito para provar que o
mecanismo de tipos de atividade funciona de ponta a ponta — os dados já bastam para
montar o roteiro no cliente hoje. Manter o escopo desta primeira entrega pequeno reduz a
superfície de mudança em `src/` antes de haver mais de um caso de uso real do roteiro
agregado.

**Alternatives considered**:
- Construir já a consulta agregada (`GET /processes/{id}/activities`): adiada
  deliberadamente; registrada como trabalho futuro no `tasks.md`, não descartada.

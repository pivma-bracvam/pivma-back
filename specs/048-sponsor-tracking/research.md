# Research: Acompanhamento do Patrocinador

Não restou `NEEDS CLARIFICATION`. As referências de linha valem para o commit
`9a60855`.

## R1. Rota própria ou extensão de `/processes`

**Decision**: router novo, `src/pivma/routers/sponsor_tracking.py`, com prefixo
`/sponsor-tracking`:

- `GET /sponsor-tracking/processes`: a lista (US1).
- `GET /sponsor-tracking/processes/{process_id}`: o detalhe (US2 e US3).

**Rationale**: o detalhe do acompanhamento junta cargos, fase e atividades,
que `ProcessInstanceDetail` não tem e que outros perfis não devem ganhar por
tabela. Um prefixo próprio deixa claro a quem a rota serve e não muda o
contrato de `GET /processes` nem de `GET /processes/{id}` (constituição VI).
`/processes/sponsored` colidiria com `/processes/{id}`, que o router de
processos declara antes e que validaria `sponsored` como UUID.

**Alternatives considered**:

- Filtro `role=sponsor` em `GET /processes`: muda `ProcessListFilters` e não
  entrega a data da designação.
- Ampliar `GET /processes/{id}/participants` para o Patrocinador: resolve o
  proponente, mas não a fase nem as atividades, e exige mudar
  `participant_read_scope`, usado também pelo histórico.
- `GET /processes/{id}/tracking`: o detalhe ficaria ao lado da linha do tempo,
  mas a lista teria de morar em outro prefixo. Duas casas para uma tela só.

## R2. Quem entra na lista

**Decision**: processos com designação de `sponsor` do usuário ativa
(`revoked_at` nulo), não excluída, com usuário ativo e processo não excluído.
A cláusula reaproveita `process_cargos_scope(user_id)`
(`src/pivma/core/authorization.py:471`) com `role_key == 'sponsor'`, como
`proponent_process_clause` faz com o proponente
(`src/pivma/core/process_engine.py:186`). Todos os estados do ciclo de vida
entram, inclusive `ARCHIVED`. A ordem segue `GET /processes`: `created_at`
decrescente, desempate por `id`.

**Rationale**: o convite pendente não cria `Assignment` (só o aceite cria),
então FR-002 sai sem filtro extra. `sponsor` não é cargo de laboratório, e
`effective_assignment_clause` deixa passar sem exigir vínculo. Admin e BraCVAM
recebem só os processos em que são Patrocinadores: a lista é "o que eu
patrocino". O processo arquivado continua na lista porque o Patrocinador
acompanha do início ao fim (Clarifications, Q2).

**Alternatives considered**: esconder `ARCHIVED` por padrão, como
`GET /processes`. Ali a regra existe porque a tela geral mistura processos
em curso. Aqui a lista é pequena e o Patrocinador perderia o processo que
acompanhou.

## R3. Cartão da lista

**Decision**: uma consulta pagina `ProcessInstance` junto com
`min(Assignment.assigned_at)` por processo, com os mesmos filtros de R2, que
vira `sponsored_since`. Outra consulta, só com os ids da página, completa
cada item: as execuções em andamento dos processos `OPEN`, pela função de
[R6](#r6-fase-atual-e-atividades-em-andamento), viram `current_phase` e
`open_activity_count`. Página sem processo `OPEN` não faz a segunda.

**Rationale**: o front pediu "informações úteis no cartão". Listas de
acompanhamento em ferramentas de gestão de projetos e de estudos clínicos
mostram, por item, o estado, a etapa atual e quanto há em aberto, e deixam
pessoas e o detalhe de cada atividade para a página do item. Fase atual e
quantidade de atividades cobrem isso sem inflar a lista. Usar a mesma função
do detalhe garante que o cartão e o detalhe nunca mostrem fases diferentes.
A data vem na mesma consulta da página: em consultas separadas, uma
revogação entre as duas deixaria o processo na página sem data.
`paginate_query` usa `session.scalars` e devolve só a primeira coluna
(`src/pivma/core/listing.py:30`), e mudar o helper para tuplas afetaria
todas as listagens. Por isso o router pagina a consulta, como
`routers/tasks.py`. São no máximo três consultas por página (total, página,
execuções), sem consulta por item.

**Alternatives considered**:

- Sem fase no cartão: o front chamaria o detalhe de cada processo, uma
  consulta por item na tela (N+1 no cliente).
- Lista completa de atividades no cartão: repete o detalhe, e a resposta
  cresce com o número de laboratórios.
- Proponente no cartão: pede mais uma consulta de designações por página. O
  detalhe já o mostra.
- Datas numa consulta à parte, depois da página: uma revogação entre as duas
  derrubava a página com erro 500.

## R4. Quem consulta o detalhe

**Decision**: o detalhe responde `200` a quem tem designação efetiva de
`sponsor` no processo e a quem tem acesso a toda a plataforma
(`has_platform_wide_access`, `src/pivma/core/authorization.py:440`). Qualquer
outro usuário recebe `404` com a mensagem de `GET /processes/{id}`
("Processo não encontrado."). Processo excluído também dá `404`.

**Rationale**: FR-009 e a constituição III. Um Colaborador do mesmo processo
já vê o cabeçalho em `GET /processes/{id}`, mas não deve ganhar a lista de
pessoas nem a posição das atividades por esta rota: a decisão da equipe vale
para o Patrocinador. `sponsored_since` vem nulo para Admin e BraCVAM sem
designação.

**Alternatives considered**: `403` para quem vê o processo por outro cargo.
Revela que a rota existe para aquele processo e diverge do padrão da API.

## R5. Pessoas por cargo

**Decision**: o detalhe traz `roles`, uma entrada por cargo do catálogo
`ParticipantRole` (`src/pivma/schemas.py:1064`), na ordem de
`typing.get_args(ParticipantRole)`, cada uma com `people`. Cada pessoa tem
`user` (`UserRef`, sem e-mail) e `laboratory` (`LaboratoryRef`, nulo fora dos
cargos de laboratório). A consulta usa as mesmas condições de
`effective_assignment_ids` (`src/pivma/core/authorization.py:672`):
designação ativa, não excluída, usuário ativo e `effective_assignment_clause`.
Dentro do cargo, a ordem é `assigned_at` e depois `id`. Os laboratórios vêm de
`laboratory_refs` (`src/pivma/core/references.py:43`).

**Rationale**: o cargo vazio aparece com `people: []`, e o front mostra "Não
atribuído" só quando não houver ninguém (edge case da spec). Usar a regra de
efetividade da autorização evita mostrar uma pessoa que o resto da API não
reconhece no cargo, como o laboratório sem vínculo ativo. A data da
designação dos outros fica de fora: a spec pede quem ocupa o cargo, não o
histórico (Assumptions).

**Alternatives considered**: listar só os cargos ocupados. O front teria de
manter a lista de cargos para mostrar os vazios, e ela já existe no backend.

## R6. Fase atual e atividades em andamento

**Decision**: uma função privada do router recebe uma lista de ids de processo
`OPEN` e busca, numa consulta, as execuções `ActivityRun.status ==
'IN_PROGRESS'` desses processos, unidas a `ActivityInstance` e `Phase`, com
`Laboratory` em junção externa. A ordem é `Phase.order_index`,
`ActivityInstance.order_index`, nome do laboratório e `ActivityRun.id`, para
ser determinística. Cada linha vira uma atividade em andamento: `key`, `name`,
`phase_key`, `started_at` (da execução) e `laboratory`. A fase atual de um
processo é a de maior `order_index` entre as linhas dele, e fica nula quando
ele não tem linha. A lista chama a função com os processos `OPEN` da página e
usa só a fase e a contagem; o detalhe chama com um id e usa as linhas.
Processo fora de `OPEN` não entra na consulta: fase nula, lista vazia,
contagem zero.

**Rationale**: o processo não guarda a etapa (`ProcessInstance`, Spec 030).
A execução `IN_PROGRESS` é o que o motor abre em toda atividade
(`_init_first_activity`, `src/pivma/core/process_engine.py:765`, e as demais
criações de `ActivityRun`). A reabertura cria execução nova, então
`started_at` já é a data da reabertura. `WAIVED`, `SUPERSEDED`, `CANCELLED` e
`COMPLETED` ficam fora pelo filtro. O cancelamento do processo cancela as
execuções (`process_engine.py:488`), e o teste de FR-006 prova que o desvio
por estado não esconde nada que deveria aparecer. Processo `OPEN` sem
execução aberta existe: no template 1, depois que o último laboratório
confirma o recebimento sem problema, nenhuma atividade fica em andamento, e a
resposta traz fase nula, como pede FR-004.

**Alternatives considered**:

- `ActivityInstance.status == 'IN_PROGRESS'`: em atividade por laboratório,
  daria uma linha só, sem o laboratório (FR-005).
- `Phase.status == 'IN_PROGRESS'` para a fase atual: as fases 2 e 3 podem
  ficar em andamento juntas enquanto houver designação aberta. A regra da
  spec (FR-004) é a fase de maior ordem com atividade aberta.

## R7. O que fica fora da resposta

**Decision**: os schemas novos têm `extra='forbid'` e só os campos do
[contrato](contracts/sponsor-tracking.md). Nenhum campo vem de `FormValue`,
`FormInstance`, `StudySubstance`, `BlindSampleCode`, `SampleReceipt`,
`Decision`, `FieldReview`, `Artifact` nem `Task`. As rotas de atividade não
mudam (FR-008).

**Rationale**: FR-007 e a constituição III. O acompanhamento é só
informativo (Clarifications): não muda nenhuma regra de acesso. Nome de atividade e nome de
laboratório não identificam substância: a equipe liberou quem participa e em
que ponto o processo está. A presença de uma execução de recebimento por
laboratório mostra que o laboratório recebeu amostras, sem quantidade, código
ou conteúdo, e não dá acesso à execução de outro laboratório.

**Alternatives considered**: um campo `activity_type` ou `execution_scope`.
Ninguém pediu, e o front não precisa deles para a tela do print.

## R8. Auditoria

**Decision**: as duas rotas são de leitura e não gravam `AuditEvent`
(FR-010). Não exigem `TrustedOrigin`, como os outros `GET`.

**Rationale**: constituição II pede evento para ação de negócio. Consulta não
é ação, e a linha do tempo de leitura não existe para outras rotas.

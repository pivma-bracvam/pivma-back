# Research: Isolamento de acesso por laboratório

## R1. Definição única de gestão do processo

**Decision**: `is_process_manager(session, user_id, process_id)` em
`authorization.py` devolve verdadeiro para Admin, BraCVAM
(`has_platform_wide_access`) e `group_manager` efetivo
(`is_effective_group_manager`). A linha do tempo, as rotas de dispensa e
reabertura e `require_laboratory_run_access` passam a chamá-lo.
`laboratory_run_visibility_clause` continua como a versão SQL da mesma regra,
para o filtro de `/tasks`; a docstring das duas aponta uma para a outra.

**Rationale**: a dupla chamada aparece hoje em dois lugares e entraria num
terceiro (FR-009). Um predicado evita que uma rota mude a definição de
gestão sem as outras.

**Alternatives considered**: converter o filtro de `/tasks` para Python.
Rejeitado: o filtro precisa ser SQL para paginar e contar facetas.

## R2. Verificação de acesso à execução de laboratório

**Decision**: `require_laboratory_run_access(session, user_id, act, run,
level='edit')`, em ordem:

1. `require_activity_access(level)`: sem ver a atividade → 404; vê mas não
   edita, ou conflito de interesse → 403 (Spec 030). Nada cita laboratório.
2. Execução sem laboratório → concede.
3. Designação efetiva de `participating_laboratory` pelo laboratório da
   execução → concede.
4. Gestão do processo (R1): `view` concede; `edit` concede só se o cargo
   global está em `edit_roles`, senão 403.
5. Qualquer outro caso → `NotFoundError(LABORATORY_RUN_NOT_FOUND)`.

`complete_laboratory_run` usa a mesma constante quando o laboratório não tem
execução. As duas respostas ficam idênticas (SC-002).

**Rationale**: quem não vê a execução recebe 404, quem vê e não edita recebe
403, a mesma convenção da Spec 030 (FR-017/FR-018). O status da execução só é
verificado depois do acesso, então uma execução concluída de outro
laboratório também responde 404.

**Alternatives considered**: 404 para o `group_manager` também ao agir.
Rejeitado: ele vê a execução em `/tasks`; 404 contradiria o que ele vê.

## R3. Uma designação de participante por usuário no processo

**Decision**: nenhuma mudança de código. O índice único `uq_assignments_active`
(processo, usuário, cargo; só designações ativas) já rejeita a segunda
designação `participating_laboratory` com `409 duplicate`, na rota de
participantes e no aceite de convite (ambos passam por `create_assignment`).
Testes passam a registrar a regra.

**Rationale**: a regra pedida coincide com a restrição existente. Uma
verificação extra em Python duplicaria o índice.

**Alternatives considered**: mensagem específica de isolamento. Rejeitado:
a mensagem atual ("Já existe uma designação ativa para este processo,
usuário e papel.") já descreve o caso.

## R4. Matriz de testes

**Decision**: um template de teste derivado de `LAB_RUN_TEMPLATE` concede
ver `receipt` a `lead_laboratory`, `statistician` e
`sample_selection_group`. Sem a concessão, esses cargos recebem 404 pela
regra da Spec 030, e o teste não provaria o filtro de laboratório. A matriz
cobre só as combinações que a suíte da Spec 036 ainda não cobre:

| Perfil | Ler execução (motor) | Concluir (motor) | `/tasks` | `/tasks/{id}` | Linha do tempo |
|---|---|---|---|---|---|
| Laboratório dono | novo | 036 | 036 | novo | 036 |
| Outro laboratório | novo | ajustado (404) | 036 | 036 | 036 |
| Laboratório líder | novo | novo | 036 | novo | novo |
| Líder por X e participante por Y | novo | novo | novo | novo | novo |
| Grupo de Seleção de Amostras | novo | novo | novo | novo | novo |
| Estatístico | novo | novo | 036 | novo | novo |
| `group_manager` | novo | 036 | 036 | novo | 036 |
| Admin | novo | 036 | novo | novo | novo |
| BraCVAM | novo | novo | 036 | novo | novo |

**Rationale**: a metodologia de testes pede granularidade por risco, sem
repetir o que já está coberto.

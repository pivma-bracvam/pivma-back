# Acompanhar o andamento de um processo

Quem tem cargo num processo acompanha em que ponto ele está por duas leituras:
a lista de processos e o andamento de um processo. As duas mostram a fase
atual e as atividades em andamento. Cada cargo vê só as pessoas e as execuções
que a [tabela de recorte](#o-que-cada-cargo-ve) libera. O acompanhamento não
muda o acesso às atividades: as rotas de amostras, de formulário e de execução
de laboratório seguem as regras de cada uma.

## Meus processos

```bash
curl -s "$API/processes?role=sponsor" -H "Authorization: Bearer $TOKEN"
```

`GET /processes` traz os processos que o usuário vê, com os filtros e o
envelope descritos em
[listagens](../referencia/listagens-e-referencias.md#processos). O filtro
`role` deixa só os processos em que o usuário tem aquele cargo efetivo. Além do
cabeçalho do processo, cada item traz:

| Campo | Conteúdo |
|---|---|
| `current_phase` | `key`, `name` e `order` da fase atual |
| `open_activity_count` | Quantas execuções em andamento o usuário vê; na Fase 3, uma por laboratório |
| `my_roles` | As designações efetivas do usuário no processo: `role_key`, `laboratory` e `assigned_at` |

O convite ainda não aceito e a designação revogada não contam em `role` nem
em `my_roles`. Os arquivados seguem a regra da lista: só aparecem com
`status=ARCHIVED`, para quem tem acesso de revisão.

## Andamento de um processo

```bash
curl -s "$API/processes/$PID/progress" -H "Authorization: Bearer $TOKEN"
```

A resposta traz:

- `my_roles`: as designações do usuário no processo, como na lista.
- `current_phase`: a fase de maior ordem que tem atividade em andamento.
- `phases`: todas as fases do processo, em ordem, com `key`, `name`, `order` e
  `status` (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED` ou `CANCELLED`).
- `roles`: os cargos que o usuário pode ver, na ordem do catálogo, com as
  pessoas que o ocupam (`user` sem e-mail e, nos cargos de laboratório,
  `laboratory`). Um cargo visível sem ninguém vem com `people: []`.
- `open_activities`: as execuções em andamento que o usuário vê, com `key`,
  `name`, `phase_key`, `started_at` e `laboratory`. Na Fase 3 há uma linha
  por laboratório. Uma execução reaberta aparece com a data da reabertura, e
  o laboratório dispensado não aparece.

`current_phase` e `phases` são iguais para todos os cargos. O item da lista e
o andamento usam a mesma regra: `open_activity_count` é igual ao tamanho de
`open_activities` para o mesmo usuário.

`current_phase` vem nulo, e `open_activities` vazia, quando o processo está
aberto sem atividade em andamento (no template 1, depois do último
recebimento confirmado) e quando está encerrado ou arquivado.

## O que cada cargo vê

| Quem | Pessoas | Execuções |
|---|---|---|
| Admin, BraCVAM, `group_manager`, `study_manager`, `sponsor` | Todos os cargos | Todas, de todos os laboratórios |
| `proponent`, `statistician`, `collaborator`, `sample_selection_group`, `regulatory_observer` | `group_manager`, `study_manager`, `sponsor`, `proponent` e o próprio cargo | As de atividade única |
| `participating_laboratory` | Os cargos acima e as pessoas do próprio laboratório | As de atividade única e as do próprio laboratório |
| `lead_laboratory` sem `participating_laboratory` | Os cargos de coordenação e a própria designação | As de atividade única |
| `adhoc_evaluator`, `peer_reviewer` | `group_manager`, `study_manager`, `sponsor` e a própria designação | As de atividade única |

Quem tem mais de um cargo no processo vê a união do que cada cargo libera.
O avaliador não vê o proponente nem outro avaliador, por causa da revisão
cega. O proponente não vê avaliador nem laboratório. Cada laboratório vê só a
própria execução, a mesma regra de `/tasks` e da linha do tempo.

## O que não aparece

As respostas não trazem e-mail, prazos, tarefas, formulários, pareceres,
decisões, substâncias, códigos cegos, SDS, recebimentos nem contagens de
amostras, para nenhum cargo. As consultas não gravam evento na linha do
tempo.

## Quem recebe `404`

O andamento responde `404` (`not_found`, "Processo não encontrado.") a quem
não vê o processo em `GET /processes/{id}`: sem designação efetiva, com a
designação revogada, e ao processo inexistente ou excluído. Admin e BraCVAM
abrem qualquer processo, com `my_roles` vazio quando não têm cargo nele.

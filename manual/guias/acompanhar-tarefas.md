# Acompanhar tarefas

`GET /tasks` é a caixa de entrada de cada usuário: lista as tarefas das
atividades que ele pode ver, em todos os processos.

## Pendências do usuário

```bash
curl -s "$API/tasks?status=READY&actionable=true" -H "Authorization: Bearer $TOKEN"
```

- `status=READY`: só abertas.
- `actionable=true`: só onde o usuário pode agir (`can_act`).
- Ordem padrão: prazo mais próximo primeiro; sem prazo, por último.

## Quadro de uma etapa

Uma chamada traz a lista, as contagens e o resumo da etapa:

```bash
curl -s "$API/tasks?phase_order=1&status=READY&include=facets&include=summary" \
  -H "Authorization: Bearer $TOKEN"
```

| Bloco | Conteúdo |
|---|---|
| `data` | Tarefas da página |
| `facets` | Contagens por `activity_key` e por `status` sobre todo o filtro |
| `summary.ai_pre_evaluation_in_progress` | Processos com pré-avaliação por IA em andamento, que não têm tarefa aberta nesse intervalo |

## Tarefas de um processo

```bash
curl -s "$API/tasks?process_id=$PID" -H "Authorization: Bearer $TOKEN"
```

Por padrão vem só a execução vigente de cada atividade. Para ver o
histórico de execuções (submissões anteriores, revisões já respondidas), use
`current_run=false`.

## Prazos vencidos

```bash
curl -s "$API/tasks?overdue=true" -H "Authorization: Bearer $TOKEN"
```

Prazo vem de `sla_hours` no template e conta a partir da abertura da
execução: 7 dias para enviar a proposta, 3 dias para a triagem e 7 dias para
responder ao retorno.

## Decidir o que mostrar

| Campo da tarefa | Use para |
|---|---|
| `can_act` | Habilitar o botão de ação |
| `activity_key` | Escolher a tela (`proposal_submission`, `triage_evaluation`…) |
| `activity_run_number` | Saber qual tentativa é (reenvio = 2, 3…) |
| `activity_run_status` | Mostrar se a execução foi concluída, dispensada ou substituída |
| `laboratory` | Identificar a execução de um laboratório (`null` nas demais) |
| `process`, `phase` | Agrupar por processo e etapa |

Todos os filtros e valores estão em
[Listagens e referências](../referencia/listagens-e-referencias.md#tarefas).

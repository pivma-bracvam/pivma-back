# Acompanhar como Patrocinador

O Patrocinador acompanha os processos que patrocina por duas rotas de
leitura. Elas mostram em que ponto o processo está e quem participa dele.
O acesso às atividades continua o mesmo: as rotas de amostras, de
formulário e de execução de laboratório recusam o Patrocinador.

## Processos que patrocino

```bash
curl -s "$API/sponsor-tracking/processes" -H "Authorization: Bearer $TOKEN"
```

A lista traz os processos em que o usuário tem designação ativa no cargo
`sponsor`, do mais novo para o mais antigo, com `page` e `per_page` do
[envelope padrão](../referencia/listagens-e-referencias.md#acompanhamento-do-patrocinador).
Os arquivados também aparecem. Cada cartão traz:

| Campo | Conteúdo |
|---|---|
| `code`, `title`, `status`, `started_at`, `closed_at` | Cabeçalho do processo |
| `sponsored_since` | Data da designação como Patrocinador |
| `current_phase` | `key`, `name` e `order` da fase atual |
| `open_activity_count` | Quantas atividades estão em andamento; na Fase 3, uma por laboratório |

O convite ainda não aceito, a designação revogada e o processo excluído
ficam fora da lista. Admin e BraCVAM só veem aqui os processos em que também
são Patrocinadores.

## Andamento de um processo

```bash
curl -s "$API/sponsor-tracking/processes/$PID" -H "Authorization: Bearer $TOKEN"
```

O detalhe repete o cabeçalho do cartão e acrescenta:

- `roles`: uma entrada por cargo, na ordem do catálogo, com as pessoas que o
  ocupam (`user` sem e-mail e, nos cargos de laboratório, `laboratory`). O
  cargo sem ninguém vem com `people: []`. O proponente aparece em
  `proponent`.
- `current_phase`: a fase de maior ordem que tem atividade em andamento.
- `open_activities`: as atividades em andamento, com `key`, `name`,
  `phase_key`, `started_at` e `laboratory`. Na Fase 3 há uma linha por
  laboratório. Uma execução reaberta aparece com a data da reabertura, e o
  laboratório dispensado não aparece.

O cartão da lista e o detalhe calculam a fase pela mesma regra:
`open_activity_count` é sempre igual ao tamanho de `open_activities`.

`current_phase` vem nulo, e a lista de atividades vazia, quando o processo
está aberto sem atividade em andamento (no template 1, depois do último
recebimento confirmado) e quando está encerrado ou arquivado.

## O que não aparece

As respostas não trazem e-mail, prazos, tarefas, formulários, pareceres,
decisões, substâncias, códigos cegos, SDS, recebimentos nem contagens de
amostras. As consultas não gravam evento na linha do tempo.

## Quem recebe `404`

O detalhe responde `404` (`not_found`, "Processo não encontrado.") a quem não
tem designação ativa de Patrocinador no processo, inclusive aos outros cargos
do mesmo processo, e ao processo inexistente ou excluído. Admin e BraCVAM
recebem `200`, com `sponsored_since` nulo quando não são Patrocinadores.

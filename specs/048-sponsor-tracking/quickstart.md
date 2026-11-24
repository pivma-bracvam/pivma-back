# Quickstart: Acompanhamento do Patrocinador

Guia de validação. O formato das respostas está no
[contrato](contracts/sponsor-tracking.md).

## Pré-requisitos

- Docker rodando (os testes sobem PostgreSQL com Testcontainers).
- `poetry install` feito.

## Jornadas

| História | Teste | O que prova |
|---|---|---|
| US1 | `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sponsor_tracking_journey.py` | o BraCVAM designa o Patrocinador; ele vê só o processo que patrocina, com a data da designação, a fase atual e a quantidade de atividades em andamento |
| US2 | mesmo arquivo | o Patrocinador vê o proponente e a Fase 2 com as designações abertas; depois da homologação, vê a Fase 3 com um recebimento por laboratório |
| US3 | mesmo arquivo | com substâncias e códigos cegos cadastrados, a resposta não contém nome químico, CAS nem código; as rotas de amostras e de formulário continuam recusando o Patrocinador |

```bash
poetry run pytest tests/integration/journeys/etapa_2_planejamento_preparacao/test_sponsor_tracking_journey.py
```

## Testes focados

```bash
poetry run pytest tests/api/routers/test_sponsor_tracking.py tests/api/routers/test_sponsor_tracking_security.py
```

Cobrem exclusões da lista, paginação e ordem, `404` por cargo, acesso de
Admin e BraCVAM, usuário desativado, laboratório sem vínculo, `WAIVED`,
reabertura, processo aberto sem atividade em andamento, encerrado, arquivado e
excluído, e a fase do cartão igual à do detalhe.

## Verificação manual no ambiente local

1. Suba a API (`poe serve`) e entre como BraCVAM.
2. Crie e envie um processo como proponente; aprove a triagem.
3. Como BraCVAM, designe um usuário em `sponsor`.
4. Como esse usuário, chame `GET /sponsor-tracking/processes`: o processo
   aparece com `sponsored_since`, `current_phase.key ==
   'phase_2_role_assignment'` e `open_activity_count` maior que zero.
5. Chame `GET /sponsor-tracking/processes/{id}`: `roles` traz o proponente,
   `current_phase.key` é `phase_2_role_assignment` e `open_activities` lista
   os `assign_*` abertos.
6. Como Colaborador do mesmo processo, chame a mesma rota: `404`.

## Fechamento

```bash
poe lint
```

```bash
poe test
```

```bash
poe docs-build
```

Os três passam e o manual descreve as rotas novas.

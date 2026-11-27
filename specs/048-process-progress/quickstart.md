# Quickstart: Andamento do processo

Guia de validação. O formato das respostas está no
[contrato](contracts/process-progress.md).

## Pré-requisitos

- Docker rodando (os testes sobem PostgreSQL com Testcontainers).
- `poetry install` feito.

## Jornadas

| História | Teste | O que prova |
|---|---|---|
| US1 | `tests/integration/journeys/etapa_2_planejamento_preparacao/test_process_progress_journey.py` | o BraCVAM designa a Patrocinadora; com `role=sponsor` ela vê só o processo que patrocina, com a designação, a fase atual e a quantidade de atividades, e o processo some quando a designação é revogada |
| US2 | mesmo arquivo | a Patrocinadora vê o proponente e a Fase 2; depois da homologação, a Fase 3 com um recebimento por laboratório |
| US3 | mesmo arquivo | com substâncias e códigos cegos cadastrados, a resposta não contém nome químico, CAS nem código; as rotas de amostras e de formulário continuam recusando a Patrocinadora |
| US4 | mesmo arquivo | o proponente vê a mesma fase sem avaliador nem laboratório; a laboratória vê só a própria equipe e o próprio recebimento |

```bash
poetry run pytest tests/integration/journeys/etapa_2_planejamento_preparacao/test_process_progress_journey.py
```

## Testes focados

```bash
poetry run pytest tests/api/routers/test_process_progress.py tests/api/routers/test_process_progress_visibility.py tests/api/routers/test_process_progress_security.py
```

Cobrem o filtro `role`, exclusões, paginação e ordem, fases com a situação,
o recorte de cada cargo, a união de cargos, `404`, Admin e BraCVAM, usuário
desativado, laboratório sem vínculo, `WAIVED`, reabertura, processo aberto
sem atividade em andamento, encerrado, arquivado e excluído, e o cartão igual
ao andamento.

## Verificação manual no ambiente local

1. Suba a API (`poe serve`) e entre como BraCVAM.
2. Crie e envie um processo como proponente; aprove a triagem.
3. Como BraCVAM, designe um usuário em `sponsor`.
4. Como esse usuário, chame `GET /processes?role=sponsor`: o processo
   aparece com `my_roles`, `current_phase.key == 'phase_2_role_assignment'`
   e `open_activity_count` maior que zero.
5. Chame `GET /processes/{id}/progress`: `roles` traz o proponente,
   `phases` traz as fases com as atividades e a situação, e os `assign_*`
   abertos aparecem com `open_runs`.
6. Como proponente, chame a mesma rota: a fase é a mesma, e não há avaliador
   nem laboratório em `roles`.

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

Os três passam e o manual descreve o andamento.

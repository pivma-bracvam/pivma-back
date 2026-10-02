# Quickstart: validar o isolamento por laboratório

## Pré-requisitos

Docker ativo (testcontainers com `pgvector/pgvector:pg17`) e dependências de
desenvolvimento instaladas.

## Rodar

```bash
pytest tests/integration/database/test_laboratory_access_matrix.py \
       tests/integration/database/test_laboratory_run_access.py \
       tests/api/routers/test_laboratory_access_matrix.py \
       tests/api/routers/test_laboratory_isolation.py -q
```

## Resultado esperado

- Cada linha de [contracts/access-matrix.md](contracts/access-matrix.md) tem
  um teste que passa.
- A conclusão da execução de B pelo laboratório A e a de um laboratório sem
  execução produzem o mesmo erro e a mesma mensagem.
- A segunda designação de participante do mesmo usuário responde `409
  duplicate`.
- A suíte da Spec 036 continua verde.

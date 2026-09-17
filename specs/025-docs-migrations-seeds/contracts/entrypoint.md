# Contrato de Execução: `entrypoint.sh`

O script `entrypoint.sh` é o ponto de entrada oficial do container Docker do backend. Ele garante a ordem estrita de operações entre DDL, baseline de dados e servidor HTTP.

## Sequência de Execução Obrigatória

```text
1. alembic upgrade head
   ├── Executa exclusivamente migrações estruturais DDL.
   └── Saída com status 0 (aborta imediatamente em caso de falha).

2. python -m pivma.bootstrap_system
   ├── Provisiona catálogo oficial: perfis, permissões e templates canônicos.
   ├── Garante idempotência: se já existirem registros, não gera erro nem duplicações.
   └── Zero processos ou dados de demonstração criados.

3. [Opcional] Validação de SEED_DEMO_DATA
   ├── Se SEED_DEMO_DATA == "true":
   │   └── python -m scripts.seeds --profile dev
   └── Caso contrário: nenhuma ação de demo.

4. exec uvicorn pivma:app --host 0.0.0.0 --port 8000
   └── Inicialização do servidor FastAPI.
```

## Tratamento de Falhas
- O script utiliza `set -e`: qualquer erro no Alembic ou no Bootstrap de sistema interrompe o container imediatamente, impedindo que a aplicação suba em estado inconsistente ou corrompido.

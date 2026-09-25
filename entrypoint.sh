#!/bin/sh
set -e

# 1. Executa exclusivamente as migrações estruturais (DDL puro)
echo "==> [1/2] Executando migrações DDL do banco de dados (Alembic)..."
alembic upgrade head

# 2. Executa o provisionamento de baseline de produção (Perfis, Permissões, Templates Canônicos)
echo "==> [2/2] Executando provisionamento canônico de sistema (Bootstrap)..."
python -m pivma.bootstrap_system

# 3. Se configurado explicitamente para ambiente de demonstração/dev, carrega dados de teste
if [ "$SEED_DEMO_DATA" = "true" ]; then
    echo "==> [Demo] Carregando massa de demonstração (SEED_DEMO_DATA=true)..."
    python -m scripts.seeds
fi

# 4. Inicia a aplicação FastAPI
echo "==> Iniciando o servidor Uvicorn..."
exec uvicorn --host 0.0.0.0 --port 8000 pivma:app
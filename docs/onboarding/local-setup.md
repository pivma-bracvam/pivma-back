# Inicialização do Ambiente Local

Este guia orienta a configuração do ambiente de desenvolvimento local do backend da PIVMA.

---

## 📋 Pré-requisitos

- **Python**: Versão `>= 3.14`
- **Gerenciador de Pacotes**: [uv](https://docs.astral.sh/uv/) (recomendado) ou [Poetry](https://python-poetry.org/)
- **Docker & Docker Compose**: Para execução do PostgreSQL 17 com extensão `pgvector`.

---

## 🚀 Inicialização Rápida com Docker Compose

A forma mais simples de subir a plataforma completa com banco de dados é via Docker Compose:

```bash
# 1. Copie as variáveis de ambiente de exemplo
cp .env.example .env

# 2. Suba os containers
docker compose up --build
```

O `entrypoint.sh` do container executa automaticamente:
1. `alembic upgrade head`: Criação de todas as tabelas e restrições estruturais.
2. `python -m pivma.bootstrap_system`: Provisionamento do baseline de produção (perfis `administrator` e `bracvam`, catálogo de permissões e templates canônicos da Fase 1).
3. `uvicorn pivma:app`: Inicialização do servidor na porta `8000`.

Acesse os serviços locais:
- **API FastAPI**: [http://localhost:8000](http://localhost:8000)
- **Swagger Interativo (OpenAPI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Hub de Demos (Referência)**: [http://localhost:8000/demos/](http://localhost:8000/demos/)

---

## 🛠️ Execução Nativa em Desenvolvimento Local

Para desenvolver o backend com recarregamento a quente (*hot-reload*):

```bash
# 1. Suba apenas o banco de dados PostgreSQL
docker compose up -d db

# 2. Instale as dependências com uv
uv sync --all-groups

# 3. Execute as migrações estruturais
uv run alembic upgrade head

# 4. Execute o bootstrap do baseline do sistema
uv run python -m pivma.bootstrap_system

# 5. (Opcional) Carregue a massa enxuta de dados de teste (6 processos)
uv run python -m scripts.seeds --profile dev

# 6. Inicie a API com live-reload
uv run fastapi dev src/pivma/__init__.py
```

---

## 📖 Visualização da Documentação MkDocs

Para ler e editar esta documentação com recarregamento em tempo real no navegador:

```bash
uv run mkdocs serve -a 0.0.0.0:8008
```

Abra [http://localhost:8008](http://localhost:8008) no seu navegador.

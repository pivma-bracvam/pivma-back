# Research: Processos de tipo aposentado na listagem e no detalhe

## R1. Causa do defeito

- **Decisão**: tratar o filtro global de soft delete como a causa imediata. Ele
  vale para o `selectinload` e devolve `template = None` quando o template tem
  `deleted_at`.
- **Evidência**: a reprodução local falhou em `processes.py:234`, a mesma linha
  do log do preview, e o banco do preview tem 3 processos `OPEN` nesse estado.

## R2. Como ler o tipo aposentado

- **Decisão**: criar `template_refs(session, version_ids)` em
  `core/references.py`, com uma consulta em lote e
  `skip_soft_delete_filter=True`.
- **Motivo**: o módulo já mostra pessoas e laboratórios desativados assim, e a
  consulta da página continua filtrando processos excluídos.
- **Alternativas descartadas**:
  - `skip_soft_delete_filter` na consulta principal, que reexibiria processos
    excluídos.
  - Exceção para templates no filtro global, que afetaria as rotas de criação e
    de catálogo.
  - Tornar `template` opcional na resposta, que quebraria o contrato e esconderia
    o tipo.
  - Tirar o soft delete do bootstrap, que manteria o tipo disponível.
  - Limpar só os dados do preview: o defeito voltaria na próxima aposentadoria.

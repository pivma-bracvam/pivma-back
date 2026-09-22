# Demonstrações do PIVMA

Páginas estáticas para demonstrar os módulos da plataforma contra a **API real**.
Totalmente desacopladas de `src/` e descartáveis a qualquer momento.

## Carregar os dados

```bash
uv run python -m scripts.seeds.seed_all
```

Um único comando prepara usuários, os cinco processos padrão e um processo em
triagem com pré-avaliação por IA executada.

## Padrão compartilhado

Contrato completo: [`../specs/015-first-deploy-baseline/contracts/demo-standard.md`](../specs/015-first-deploy-baseline/contracts/demo-standard.md).

- Estilo em `assets/base.css`; status da API em `assets/base.js`
  (`<span class="api-status" data-api-status>`).
- Cada página: cabeçalho + status → uma frase de propósito → passos numerados
  curtos → chamada de ação.
- Textos em português; termo em inglês só sem equivalente de uso corrente.
- Página sem dados carregados mostra o aviso único de `assets/base.js`
  (`window.showNeedsSeed`), nunca um erro cru.
- Sem endpoint facilitador na API; sem simulação de dados no frontend.

## Páginas

| # | Pasta | Papel |
| :- | :- | :- |
| 1 | `forms/` | Editor de formulário + configuração de IA |
| 2 | `submission/` | Submissão + pré-avaliação por IA |
| 3 | `triage/` | Triagem técnica &amp; decisão |
| 4 | `ai-pipeline/` | Observabilidade de IA |
| 5 | `users/` | Usuários e RBAC |
| 6 | `operational-index/` | Índice operacional (consulta periódica de logs) |
| 7 | `attachments/` | Anexos de formulário |
| 8 | `roadmap/` | Roteiro em duas fases (prévia) |
| 9 | `kanban/` | Kanban de pendências |
| 10 | `submission-update/` | Atualização integral e parcial de submissão |

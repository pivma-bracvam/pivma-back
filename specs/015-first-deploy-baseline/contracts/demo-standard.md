# Contrato de Interface — Padrão Compartilhado das Demos

Este é o contrato que as seis páginas de `demos/` devem cumprir. Ele é a base do
checklist de "padrão consistente" (SC‑004) e substitui, em forma mínima, o `DESIGN.md`
removido — que **não** deve ser recriado.

## Escopo

Páginas cobertas (todas em `demos/`):

| Página | Pasta | Papel |
| :-- | :-- | :-- |
| Editor de Formulário + Configuração de IA | `forms/` | ciclo principal |
| Submissão + Pré-avaliação por IA | `submission/` | ciclo principal |
| Triagem Técnica & Decisão | `triage/` | ciclo principal |
| Observabilidade de IA | `ai-pipeline/` | ciclo principal |
| Gestão de Usuários e RBAC | `users/` | apoio |
| Índice Operacional (Logs SSE) | `operational-index/` | apoio |

Nenhuma página nova é criada.

## Assets compartilhados

- `demos/assets/base.css` — tokens de cor, tipografia, cabeçalho, cartões, botões,
  tabelas, badge de status. Fonte única de estilo; páginas não redefinem esses tokens.
- `demos/assets/base.js` (opcional) — componente de status da API (`GET /` →
  online/offline/erro), hoje duplicado em cada página.
- Ambos servidos estaticamente sob `/demos/assets/`. **Proibido** qualquer `import` de
  `src/` ou dependência de build.

## Esqueleto obrigatório de cada página

1. **Cabeçalho**: título curto da demo (≤ 5 palavras) + badge de status da API.
2. **Uma frase** dizendo o que a demo mostra.
3. **Passos numerados curtos** (rótulos e botões, não parágrafos).
4. **Chamada de ação** para o próximo passo do ciclo (quando houver).

## Regras

| # | Regra | Verificação |
| :-- | :-- | :-- |
| C1 | Mesma paleta, tipografia, cabeçalho e badge de status em todas as páginas (via `base.css`). | Inspeção visual + `grep` por `<link rel="stylesheet" href="/demos/assets/base.css">` nas 6 páginas. |
| C2 | Textos da interface em português; termo em inglês só sem equivalente de uso corrente. | Revisão de texto das 6 páginas. |
| C3 | Conteúdo enxuto: sem parágrafos explicativos longos; preferir passos e rótulos. | Revisão de texto. |
| C4 | Toda instrução de carga de dados usa exatamente `uv run python -m scripts.seeds.seed_all`. | `grep -rn "seed_all" demos/` → todas as ocorrências idênticas. |
| C5 | Página aberta sem massa de dados mostra uma mensagem única e orientadora citando o comando C4 (não um erro cru). | Abrir cada demo com banco vazio. |
| C6 | Catálogo `demos/index.html` lista as 6 páginas, cada uma com descrição de 1 linha, sem link quebrado. | Abrir o catálogo; clicar em todos os links. |
| C7 | Zero referências a `DESIGN.md` em `demos/`. | `grep -rn "DESIGN.md" demos/` → vazio. |
| C8 | Páginas consomem apenas a API real; sem simulação de dados no frontend e sem endpoint facilitador. | Revisão de código; Constituição II. |
| C9 | Contas de teste exibidas onde forem úteis: `admin` / `Admin@123456`, `proponent_user` / `Proponent@123456`, `triage_evaluator` / `Triage@123456`. | Inspeção. |

## Comando de carga canônico

```bash
uv run python -m scripts.seeds.seed_all
```

Paridade com Poetry mantida (`poetry run python -m scripts.seeds.seed_all`), mas o
texto exibido nas demos e no catálogo cita a forma `uv`.

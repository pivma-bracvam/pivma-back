# Contrato — Payload da pré-avaliação (conteúdo avaliado)

`GET /processes/{id}/pre-evaluation` → `PreEvaluationResponse`.

## Campo `evaluated_content` (já existe desde a Spec 013; muda a origem)

```jsonc
"evaluated_content": [
  { "field_key": "scope_extension_justification",
    "label": "Justificativa da Extensão de Escopo",
    "value": "texto submetido pelo proponente" }
]
```

Schema item: `EvaluatedContentField { field_key: str, label: str, value: Any }` —
inalterado.

### Regra de resolução (nova)

1. Se `evaluation_runs.evaluated_content_snapshot` **não é nulo** → devolve o
   snapshot verbatim.
2. Senão → devolve `await _evaluated_content(session, run)` (reconstrução a partir
   da `FormInstance` imutável + associações **atuais**) — caminho de compatibilidade
   para execuções anteriores à migração e execuções `failed`.

O consumidor não distingue os dois casos. Opcional: expor
`evaluated_content_source: "snapshot" | "reconstructed"` para transparência na
demo — **decisão adiada para /speckit-tasks**; não é requisito.

## Invariante testável (US3 / SC-006)

Dada uma execução concluída **após** a migração:

```
run_1 = executa pré-avaliação           # snapshot gravado
c1 = GET .../pre-evaluation .evaluated_content
altera associação do template (remove o campo / troca a definição)
c2 = GET .../pre-evaluation .evaluated_content   # mesma execução
assert c1 == c2                          # snapshot não muda
```

Dada uma execução **sem** snapshot (pré-migração, simulada com a coluna em NULL):

```
c = GET .../pre-evaluation .evaluated_content
assert c == reconstrução atual           # fallback, sem erro
```

## Resposta de submissão (remoção — Spec 010)

`POST /processes/{id}/activities/{activity_key}/form` → `ActivityCompletionResponse`.

| Campo | Antes | Depois |
|---|---|---|
| `activity_key` | ✅ | ✅ |
| `run_number` | ✅ | ✅ |
| `status` | ✅ | ✅ |
| `artifact_id` | ✅ | ✅ |
| `pre_evaluation` | `{run_id, status}` \| `null` | inalterado |
| `ai_evaluation` | objeto do parecer legado \| `null` | **REMOVIDO** |

`GET /processes/{id}/activities/{activity_key}/form` (`FormInstanceResponse` /
o schema de detalhe do formulário): remover o campo `ai_evaluation` do retorno.
O dado histórico permanece em `artifact.metadata_payload['ai_evaluation']` para
processos antigos, apenas não é mais exposto por esta rota.

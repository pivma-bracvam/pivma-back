# Contrato: pareceres da submissão

Campos aditivos. Status, permissões e erros não mudam.

## `FieldReviewSummary`

```json
{
  "status": "NAO_CONFORME",
  "comments": "Detalhar o protocolo.",
  "reviewed_at": "2026-11-06T14:00:00"
}
```

Nenhuma resposta traz o autor.

## `GET /processes/{id}/activities/{activity_key}/form`

Novo campo `previous_reviews`, um objeto de `field_key` para
`FieldReviewSummary`.

- Em `proposal_submission`: pareceres da execução anterior à resolvida. Com
  `?run_number=N`, os da execução `N-1`.
- Vazio na primeira rodada, em rodada anterior sem pareceres e nas demais
  atividades.
- Pode trazer chave ausente de `fields`, quando o campo saiu da definição.

`reviews` não muda.

## `GET /processes/{id}/submission-versions/{run_number}`

Novo campo `reviews`, no mesmo formato, com os pareceres daquela execução. Só
entram pareceres de execução da triagem concluída. Vazio em versão devolvida
pela IA enquanto a triagem não decide uma contestação.

## Sem mudança

- `GET /processes/{id}/submission-versions`
- `GET /processes/{id}/return-review`, inclusive o `404` depois da decisão

# Contratos afetados

## `GET /processes/templates`

Sem mudança de rota, permissão, parâmetros ou campos dos itens.

Mudanças:

- `data` traz 4 itens, na ordem de `display_order`, com desempate por `key`.
- `pagination.total_items` passa de 5 para 4.
- `sort` passa de `{"by": "name", "order": "asc"}` para
  `{"by": "display_order", "order": "asc"}`.

Exemplo:

```json
{
  "data": [
    {"id": "…", "key": "pre_validated_method", "name": "Método Novo", "description": "Método em desenvolvimento ou já desenvolvido, cujo processo de validação ainda não foi executado.", "is_active": true},
    {"id": "…", "key": "validated_method_dossier", "name": "Método Novo – Dossiê Completo", "description": "…", "is_active": true},
    {"id": "…", "key": "scope_extension", "name": "Extensão do Domínio de Aplicação", "description": "…", "is_active": true},
    {"id": "…", "key": "me_too_validation", "name": "Método Similar", "description": "…", "is_active": true}
  ],
  "pagination": {"page": 1, "per_page": 20, "total_items": 4, "…": "…"},
  "filters_applied": {},
  "sort": {"by": "display_order", "order": "asc"}
}
```

## `GET /processes/templates/proof_of_concept`

Passa a responder 404 ("Template não encontrado."), como
qualquer chave inexistente.

## `POST /processes` com `template_key: "proof_of_concept"`

Passa a responder 404 ("Template não encontrado ou inativo."), sem criar
processo.

## `POST /processes` (código)

Sem mudança de esquema. O campo `code` da resposta segue o formato
`VAL-<ano>-<n:04d>`, com o ano no horário de Brasília. O mesmo valor aparece
em listagens, detalhes, notificações e e-mails que já exibem o código.

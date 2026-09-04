# Contrato HTTP: Submissão de Método Alternativo

Todos os endpoints exigem a autenticação existente. Enquanto o processo permanece em elaboração (`status = SUBMISSION`), somente o proponente ativo e eficaz da instância acessa os recursos da submissão. Após a instância deixar `SUBMISSION` (por exemplo, ao entrar em triagem via envio formal), esta feature não restringe o acesso além do que já existia antes de RF007; essa restrição pertence a outra feature.

## Sequência para o frontend

1. Criar: `POST /processes`.
2. Renderizar definição e valores: `GET /processes/{process_id}/activities/proposal_submission/form`.
3. Salvar rascunho parcial: `PUT /processes/{process_id}/activities/proposal_submission/form`.

O frontend usa `fields[*].field_key` como chave do objeto `values`. Não deve manter uma lista fixa de campos científicos. `field_type`, `options` e `validation_rules` permitem escolher componente e validação de interface; o backend continua sendo a autoridade da validação.

## Criar submissão

`POST /processes`

```json
{
  "template_key": "full_validation",
  "title": "Método de irritação cutânea"
}
```

Resposta `201`:

```json
{
  "id": "uuid",
  "code": "VAL-2026-1a2b3c4d5e6f7a8b",
  "title": "Método de irritação cutânea",
  "status": "SUBMISSION",
  "template_key": "full_validation",
  "version_number": 1,
  "started_at": "2026-09-04T12:00:00Z",
  "closed_at": null,
  "closure_reason": null
}
```

`code` é o `crCode`. A resposta não cria documento, não conclui formulário e não inicia triagem.

## Consultar submissões próprias

- `GET /processes?page=1&size=20&status=SUBMISSION`
- `GET /processes/{process_id}`
- `GET /processes/{process_id}/timeline`

Essas respostas preservam os schemas já existentes. A lista inclui somente processos em que o solicitante é proponente ativo e eficaz; `total` e paginação são calculados depois desse filtro.

## Consultar formulário dinâmico

`GET /processes/{process_id}/activities/proposal_submission/form`

Resposta `200`:

```json
{
  "form_instance_id": "uuid",
  "template_key": "submission_full_validation_v1",
  "is_submitted": false,
  "fields": [
    {
      "field_key": "endpoint_target",
      "label": "Desfecho / Toxicidade Avaliada",
      "help_text": null,
      "field_type": "select",
      "is_required": true,
      "order_index": 2,
      "options": [{"value": "skin_sensitization", "label": "Sensibilização Cutânea"}],
      "validation_rules": null
    }
  ],
  "values": {"endpoint_target": "skin_sensitization"},
  "reviews": {}
}
```

O frontend pode exibir a presença de `file_upload`, mas não envia valor para esse tipo durante RF007. O produto definirá anexação em RF008.

## Salvar rascunho parcial

`PUT /processes/{process_id}/activities/proposal_submission/form`

```json
{
  "values": {
    "method_title": "Método em elaboração",
    "endpoint_target": "skin_sensitization",
    "expected_laboratories_count": 3
  }
}
```

Resposta `200` mantém o contrato atual:

```json
{
  "message": "Rascunho salvo com sucesso.",
  "form_instance_id": "uuid"
}
```

Valores omitidos permanecem como estavam. `null` limpa um valor enviado anteriormente. Campos obrigatórios podem ficar ausentes no rascunho.

## Erros

| Status | Situação | Corpo esperado |
|---|---|---|
| `404` | Processo, atividade ou formulário ausente; ou, enquanto `status = SUBMISSION`, solicitante sem proponente ativo e eficaz. | `{"detail":"Processo não encontrado."}` ou mensagem equivalente que não revele o recurso protegido. |
| `409` | Formulário já submetido. | Contrato atual de conflito. |
| `422` | Uma ou mais chaves são desconhecidas, tipos/opções/regras são inválidos, ou há tentativa de valor `file_upload` no `PUT`. | `{"detail":{"code":"invalid_form_values","errors":[{"field_key":"endpoint_target","code":"invalid_option","message":"..."}]}}` |

Em `422` de validação de rascunho, o backend não grava nenhum valor do pedido. O frontend associa erros por `field_key`; ele não deve presumir que valores válidos do mesmo payload foram salvos. Esse `detail` é sempre um **objeto** (`{"code", "errors"}`). Um `422` de corpo malformado (JSON inválido, campo obrigatório do schema do endpoint ausente) continua sendo o formato padrão do FastAPI, com `detail` como **lista**; o frontend deve distinguir os dois formatos antes de tentar ler `detail.errors`.

`POST /processes/{id}/activities/{activity_key}/form` permanece fora da sequência de RF007 e pertence ao envio formal. Esta feature aplica a mesma proteção contextual a ele (enquanto `status = SUBMISSION`) para impedir que um terceiro execute a operação em uma submissão protegida; não altera seus efeitos de workflow. Diferente do `PUT` de rascunho, esse endpoint continua aceitando valor para `study_protocol_file` como texto, no comportamento já existente antes de RF007; RF008 tratará a anexação real.

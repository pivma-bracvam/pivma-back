# Contrato HTTP: Spec 040

Erros no formato único `{"detail": {"code", "message", "fields"?}}`.
Rotas de escrita exigem sessão e `Origin` confiável. Listagens usam o
envelope paginado (`data`, `pagination`, `filters_applied`, `sort`).

## Amostras (Grupo de Seleção) — mudanças

Acesso igual ao da Spec 031: concessão de edição de `sample_definition`.

### `POST /processes/{id}/samples` e `PATCH /processes/{id}/samples/{substance_id}`

Campos novos no corpo (todos opcionais na alteração):

```json
{
  "reference_classification": "Severamente irritante / Categoria 1",
  "storage_temperature_regime": "refrigerated",
  "storage_temperature_min": 2.0,
  "storage_temperature_max": 8.0,
  "vial_nominal_quantity": 50,
  "vial_unit": "mL",
  "packaging_type": "Frasco de vidro âmbar com lacre inviolável",
  "expiration_date": "2027-03-31",
  "reserve_vials_count": 2,
  "ghs_hazard_pictograms": ["GHS05", "GHS06"]
}
```

- `reference_classification`: obrigatória no `POST`; no `PATCH`, se enviada,
  não pode ser nula nem vazia.
- `422` com `fields`: classificação ausente ou vazia, pictograma inválido ou
  repetido, número negativo, quantidade zero, regime desconhecido.
- `422 invalid_temperature_range`: mínimo > máximo, faixa sem regime ou
  regime que exige faixa sem ela (também na alteração, sobre o estado
  resultante).

Resposta (`SampleSubstance`) ganha os mesmos campos.

### `GET /processes/{id}/samples/lookup?cas=50-00-0`

Sugestões do PubChem. Não grava nada.

```json
{
  "cas_number": "50-00-0",
  "source": "pubchem",
  "pubchem_cid": 712,
  "source_url": "https://pubchem.ncbi.nlm.nih.gov/compound/712",
  "chemical_name": "Formaldehyde",
  "iupac_name": "formaldehyde",
  "ghs_hazard_pictograms": ["GHS05", "GHS06", "GHS08"]
}
```

- `422 invalid_cas`: CAS inválido; a fonte não é chamada.
- `404 compound_not_found`: a fonte não conhece o CAS.
- `503 lookup_unavailable`: fonte fora do ar, erro, formato inesperado ou
  tempo esgotado.
- `404`/`403`: mesmo acesso das demais rotas de amostras.

### `GET /processes/{id}/samples/labels`

Cada etiqueta ganha `ghs_hazard_pictograms`, `storage_temperature_regime`,
`storage_temperature_min`, `storage_temperature_max`,
`vial_nominal_quantity`, `vial_unit`, `packaging_type`, `expiration_date`.

### `GET /processes/{id}/samples/vials/{code}` (visão cega)

Acesso: Grupo de Seleção (como antes) **ou** pessoa com designação efetiva
de `participating_laboratory` pelo laboratório do código. Para qualquer
outro laboratório ou código inexistente: `404`.

```json
{
  "code": "XR3921KM",
  "lot": "L-2026-04",
  "safe_handling_instructions": "Usar luvas nitrílicas e capela.",
  "ghs_hazard_pictograms": ["GHS05"],
  "storage_temperature_regime": "refrigerated",
  "storage_temperature_min": 2.0,
  "storage_temperature_max": 8.0,
  "vial_nominal_quantity": 50.0,
  "vial_unit": "mL",
  "packaging_type": "Frasco âmbar",
  "expiration_date": "2027-03-31"
}
```

Nunca: nome químico, CAS, SDS, classificação de referência.

## Recebimento (laboratório participante)

Acesso: designação efetiva de `participating_laboratory` no processo. A
concessão da atividade `sample_receipt` vale primeiro (Spec 030): sem ela,
`404`.

### `GET /processes/{id}/sample-receipt/vials?search=`

Frascos dos laboratórios do usuário, ordenados por laboratório e código.
`search` (1 a 8 caracteres) filtra por trecho do código, sem diferenciar
maiúsculas. Cada item traz também `lot`, `safe_handling_instructions` e os
campos de conservação da visão cega (`ghs_hazard_pictograms`,
`storage_temperature_*`, `vial_*`, `packaging_type`, `expiration_date`).
`filters_applied` = `{"search": ...}`.

```json
{
  "data": [
    {
      "code": "XR3921KM",
      "laboratory": {"id": "…", "name": "Lab A"},
      "status": "pending",
      "receipt": null,
      "photos": []
    },
    {
      "code": "B7Q2M9TC",
      "laboratory": {"id": "…", "name": "Lab A"},
      "status": "awaiting_decision",
      "receipt": {
        "id": "…",
        "opened_at": "2026-10-04T09:30:00Z",
        "temperature_celsius": 21.0,
        "package_state": "intact",
        "notes": "Gelo totalmente fundido.",
        "conforming": false,
        "deviations": ["temperature_out_of_range"],
        "registered_at": "2026-10-04T09:41:00Z"
      },
      "photos": [{"id": "…", "filename": "frasco.jpg", "size": 1234}],
      "lab_guidance": null
    }
  ],
  "pagination": {"page": 1, "per_page": 20, "total": 2, "pages": 1},
  "filters_applied": {},
  "sort": {"by": "laboratory", "order": "asc"}
}
```

`status`: `pending`, `received`, `awaiting_decision`, `accepted_with_caveat`,
`replaced`, `disqualified`. Nunca a justificativa nem o código substituto.
`lab_guidance` traz a orientação do Grupo depois da decisão (FR-048).

### `POST /processes/{id}/sample-receipt/vials/{code}/check` → `200`

Pré-verificação: mesmo corpo, mesmas recusas (`422`, `404`, `409`) do
registro. Nada é gravado.

```json
{
  "conforming": false,
  "deviations": ["temperature_out_of_range"],
  "message": "Condição fora do padrão no frasco B7Q2M9TC: temperatura fora da faixa (esperado de 2 °C a 8 °C). Ao confirmar, uma inconformidade será registrada automaticamente e a equipe responsável pelas amostras será avisada."
}
```

### `POST /processes/{id}/sample-receipt/vials/{code}` → `201`

```json
{
  "opened_at": "2026-10-04T09:30:00Z",
  "temperature_celsius": 21.0,
  "package_state": "intact",
  "notes": "Gelo totalmente fundido, temperatura ambiente atingida durante o frete."
}
```

- `opened_at` obrigatório, não futuro; `temperature_celsius` numérico
  obrigatório; `package_state` em `intact`, `damaged`, `violated`;
  `notes` opcional. Faltas e formatos: `422` com `fields`.
- `404`: código de outro laboratório, inexistente ou inativo.
- `409 vial_already_registered`: o frasco já tem registro.
- `409 invalid_transition`: recebimento do laboratório fora de andamento
  (bloqueado, concluído, dispensado) ou processo imutável.

Resposta:

```json
{
  "vial": {"code": "…", "laboratory": {…}, "status": "awaiting_decision", "receipt": {…}, "photos": []},
  "conforming": false,
  "deviations": ["temperature_out_of_range"],
  "laboratory_receipt_status": "awaiting_decision",
  "message": "Registramos o reporte de avaria/desvio no frasco B7Q2M9TC. A equipe responsável pelas amostras foi notificada e está avaliando o caso. Mantenha o material segregado e aguarde as orientações, que serão emitidas aqui na plataforma."
}
```

`laboratory_receipt_status`: `in_progress` (há frasco pendente),
`awaiting_decision` (há inconformidade aberta), `completed` (lote fechado).
Em `completed`, a mensagem diz que o lote foi registrado na cadeia de
custódia e está liberado para os ensaios.

### `POST /processes/{id}/sample-receipt/vials/{code}/photos` → `201`

`multipart/form-data`, campo `file`; `png`, `jpg`, `jpeg`, até
`ATTACHMENT_MAX_SIZE_MB`.

- `404`: frasco de outro laboratório ou sem registro.
- `409 invalid_transition`: recebimento do laboratório fora de andamento.
- `422 extension_not_allowed`, `413`/`422 file_too_large`, `422 empty_file`
  (mesmos códigos dos anexos da Spec 016).

Resposta: `{"id", "filename", "size", "uploaded_at"}`.

### `GET /processes/{id}/sample-receipt/photos/{photo_id}`

Download. Acesso: o laboratório do registro e o Grupo de Seleção. Demais:
`404`.

## Inconformidades (Grupo de Seleção)

Acesso: concessão de edição de `sample_receipt_resolution` (Grupo de
Seleção). Admin e BraCVAM veem a atividade, mas recebem `403`; os demais,
`404`.

### `GET /processes/{id}/sample-receipt/nonconformities?status=open|resolved`

Ordenadas por data de abertura (mais antiga primeiro).

```json
{
  "data": [
    {
      "id": "…",
      "status": "OPEN",
      "alert": "Alerta de Recebimento: o laboratório Lab A registrou desvio térmico no frasco B7Q2M9TC.",
      "laboratory": {"id": "…", "name": "Lab A"},
      "code": "B7Q2M9TC",
      "substance": {"id": "…", "chemical_name": "Formaldeído", "cas_number": "50-00-0", "reserve_vials_count": 2},
      "expected_temperature": {"regime": "refrigerated", "min": 2.0, "max": 8.0},
      "receipt": {…},
      "photos": […],
      "deviations": ["temperature_out_of_range"],
      "opened_at": "…",
      "decision": null,
      "justification": null,
      "lab_guidance": null,
      "decided_by": null,
      "decided_at": null,
      "replacement_code": null
    }
  ],
  "pagination": {…},
  "filters_applied": {"status": "open"},
  "sort": {"by": "opened_at", "order": "asc"}
}
```

### `POST /processes/{id}/sample-receipt/nonconformities/{nc_id}/decision`

```json
{"decision": "resend", "justification": "Frasco reserva despachado em 05/10.",
 "lab_guidance": "Descarte o frasco antigo como resíduo químico."}
```

- `decision` em `accept_with_caveat`, `resend`, `disqualify`;
  `justification` obrigatória, não vazia (`422` com `fields`).
- `lab_guidance` opcional; vazia ou só com espaços vira `null`. O
  laboratório a vê no frasco e recebe e-mail `sample_receipt_decision_email`
  com a situação e a orientação (FR-047 a FR-049).
- `404`: inconformidade de outro processo ou inexistente.
- `409 already_decided`: inconformidade já resolvida.
- `409 no_reserve_vials`: reenvio com reserva zero.
- `409 invalid_transition`: processo imutável.

Resposta `200`: a inconformidade atualizada (mesmo formato da lista).

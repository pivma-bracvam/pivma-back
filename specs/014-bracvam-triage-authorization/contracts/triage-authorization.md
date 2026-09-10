# Contrato — Autorização da triagem

Permissão nova: **`triage.review`**. Detentores por padrão: perfis `bracvam` e
`administrator`. Nenhuma rota nova; apenas guardas adicionadas/trocadas.

## Rotas afetadas

### `POST /processes/{id}/triage/reviews`
- **Antes**: `CurrentUser` (autenticado) + guarda de conflito de interesse.
- **Depois**: `Depends(require_permission('triage.review'))` + `CurrentUser` +
  `TrustedOrigin` + guarda de conflito.
- **403** (`{"detail": "Forbidden"}`) se o usuário não tem `triage.review`.
- **403** (`{"detail": "Usuário com conflito de interesse vigente neste processo."}`)
  se tem a permissão mas conflito vigente.
- **200** `{"message": "Avaliações de campo registradas com sucesso."}` no sucesso.

### `POST /processes/{id}/triage/decision`
- **Antes**: `CurrentUser` + conflito.
- **Depois**: `require_permission('triage.review')` + `CurrentUser` +
  `TrustedOrigin` + conflito.
- **403** / **409** / **422** inalterados nos demais casos.
- **200** `TriageDecisionResponse` no sucesso.

> Nota: `triage.py` hoje não declara `TrustedOrigin`. Adicionar `_origin: TrustedOrigin`
> às duas rotas (mutação protegida — Princípio VI). Verificar se algum teste
> existente chama sem header `Origin` e ajustar (`{'Origin': 'https://testserver'}`).

### `GET /processes/{id}/pre-evaluation`
- **Antes** (`_ensure_can_read`): `is_active_effective_proponent` ∨
  `is_effective_group_manager` ∨ `has_permission('ai_evaluations.read')`.
- **Depois**: `is_active_effective_proponent(session, user, id)` ∨
  `has_permission(session, user, 'triage.review')`.
- **403** (`{"detail": "Sem acesso à pré-avaliação deste processo."}`) caso
  contrário.

### `POST /processes/{id}/pre-evaluation/{run_id}/feedback`
- **Antes**: `is_effective_group_manager` ∨ `has_permission('ai_evaluations.read')`.
- **Depois**: `has_permission(session, user, 'triage.review')`.
- **403** (`{"detail": "Apenas o BraCVAM registra feedback da pré-avaliação."}`)
  — atualizar a mensagem (era "gestores do BraCVAM").
- Guarda de conflito no serviço (`has_current_conflict`) inalterada → **403**
  (`AuthorizationError`) se conflito vigente.

### `/ai-evaluations/**` (config)
- Sem mudança de código. O perfil `bracvam` passa a satisfazer
  `require_permission('ai_evaluations.read'/'manage')` por já deter as permissões
  (composição na migração).

## Matriz de acesso (resultado esperado)

| Usuário | reviews | decision | GET pre-eval (proc. X) | feedback |
|---|---|---|---|---|
| Perfil `bracvam`, sem conflito | ✅ | ✅ | ✅ | ✅ |
| Perfil `administrator`, sem conflito | ✅ | ✅ | ✅ | ✅ |
| Perfil `bracvam`, **com conflito** em X | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Perfil `management_group` (Grupo Gestor) | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| Perfil `reviewer` (Revisor) | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| Proponente ativo de X | ❌ 403 | ❌ 403 | ✅ (só o próprio) | ❌ 403 |
| Proponente de outro processo | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| Autenticado sem perfil | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |

## Constante

`src/pivma/core/authorization.py`:
```python
TRIAGE_REVIEW = 'triage.review'
```

# Administrar usuários e acessos

Tarefas do Administrador. O BraCVAM também tem todas as permissões, mas as
rotas marcadas com "só Administrador" checam o perfil, não a permissão.

## Primeiro administrador

Escolha uma das formas:

| Forma | Como |
|---|---|
| Na implantação | Defina `INITIAL_ADMIN_EMAIL` e `INITIAL_ADMIN_PASSWORD` (e, se quiser, `INITIAL_ADMIN_USERNAME`). O `bootstrap_system` cria a conta e dá o perfil. No Docker, ele roda a cada subida da API |
| Conta já cadastrada | `poetry run python -m pivma.bootstrap_rbac --user-id <UUID>`. Idempotente; recusa se outra conta ativa já for administradora |

## Contas

| Ação | Rota | Permissão |
|---|---|---|
| Listar | `GET /users?search=&active=true&profile_id=` | `users.read` |
| Alterar `username`, `email`, `full_name` ou `password` | `PATCH /users/{id}` | `users.manage` |
| Desativar | `DELETE /users/{id}` | `users.manage` |

A desativação preserva o registro e libera `username` e `email` para novos
cadastros. Conta inativa não entra e não usa tokens antigos. Não é possível
desativar a si mesmo (`409 self_deactivation`) nem a última conta
administradora ativa (`409 last_administrator`). `GET /users?active=false`
lista as inativas.

## Perfis globais

| Ação | Rota |
|---|---|
| Listar permissões | `GET /rbac/permissions` |
| Listar perfis | `GET /rbac/profiles` |
| Criar perfil | `POST /rbac/profiles` com `name`, `description`, `permission_codes` |
| Alterar | `PATCH /rbac/profiles/{id}` |
| Desativar | `DELETE /rbac/profiles/{id}` |
| Dar perfil a um usuário | `POST /rbac/users/{user_id}/profiles/{profile_id}` |
| Tirar | `DELETE /rbac/users/{user_id}/profiles/{profile_id}` |
| Acesso efetivo de um usuário | `GET /rbac/users/{user_id}/access` |
| Histórico de mudanças | `GET /rbac/changes` |

Restrições:

- `Administrador` e `BraCVAM` são perfis oficiais: o nome não muda e não pode
  ser reutilizado (`409 duplicate`). O Administrador não pode ser desativado.
- Os dois oficiais têm todas as permissões ativas, incluindo as criadas no
  futuro. Perfis criados aqui têm só as permissões listadas.
- Ids fixos: Administrador `00000000-0000-0000-0000-000000000009`,
  BraCVAM `00000000-0000-0000-0000-00000000000a`.

A lista de permissões está em
[Perfis, permissões e cargos](../referencia/perfis-permissoes-cargos.md).

## Instituições e laboratórios

| Ação | Rota | Permissão |
|---|---|---|
| Listar e ler | `GET /institutional/institutions`, `GET /institutional/laboratories` | `institutional.read` |
| Criar instituição | `POST /institutional/institutions` com `name` | `institutional.catalogs.manage` |
| Criar laboratório | `POST /institutional/laboratories` com `institution_id`, `name` | `institutional.catalogs.manage` |
| Alterar, desativar | `PATCH` / `DELETE` em `.../{id}` | `institutional.catalogs.manage` |
| Histórico | `GET /institutional/changes` | `institutional.read` |

Nome repetido responde `409 duplicate`.

## Vincular a um laboratório

Cargos de laboratório exigem que o usuário esteja vinculado ao laboratório:

```bash
curl -s -X POST $API/institutional/users/$USER_ID/affiliations \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"institution_id":"…","laboratory_id":"…"}'
```

| Ação | Rota | Permissão |
|---|---|---|
| Vincular | `POST /institutional/users/{id}/affiliations` | `institutional.affiliations.manage` |
| Encerrar | `DELETE /institutional/users/{id}/affiliations/{affiliation_id}` | `institutional.affiliations.manage` |
| Ver os vínculos de alguém | `GET /institutional/users/{id}/affiliations` | `institutional.read` |
| Ver os próprios | `GET /institutional/me/affiliations` | Sessão |

O laboratório precisa pertencer à instituição informada (`409`).

!!! warning "Efeito sobre processos em andamento"
    Encerrar um vínculo, ou desativar o laboratório ou a instituição, retira
    no pedido seguinte o acesso que dependia do cargo de laboratório, sem
    revogar a designação. Um novo vínculo com o mesmo laboratório devolve o
    acesso. Veja [designação efetiva](../explicacao/autorizacao.md#designacao-efetiva).

## Editar campos de formulário

Quem tem `form_templates.manage` (ou é Administrador) altera a definição de
um formulário:

```bash
curl -s -X PUT $API/processes/templates/$TEMPLATE_KEY/forms/$FORM_KEY \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d @campos.json
```

O corpo traz `fields` e, se quiser, `name` e `description`. A estrutura das
fases e atividades não muda pela API; ela vem dos arquivos YAML (veja
[Sintaxe dos templates](../referencia/templates-yaml.md)).

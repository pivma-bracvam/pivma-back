# Contrato: acesso à execução de um laboratório

Execução do laboratório B numa atividade por laboratório. Todos os perfis
têm a concessão de ver a atividade; os laboratoriais também a de editar.

| Perfil | `/tasks` | `/tasks/{id}` | Eventos de B na linha do tempo | Ler execução | Concluir execução |
|---|---|---|---|---|---|
| Participante efetivo por B | lista | 200 | vê | concede | concede |
| Participante efetivo por A | não lista | 404 | não vê | 404 | 404 |
| Participante por B sem vínculo ativo | não lista | 404 | não vê | 404 | 404 |
| Laboratório líder (qualquer laboratório) | não lista | 404 | não vê | 404 | 403 da atividade¹ |
| Líder por B e participante por A | não lista | 404 | não vê | 404 | 404 |
| Grupo de Seleção de Amostras | não lista | 404 | não vê | 404 | 403 da atividade¹ |
| Estatístico | não lista | 404 | não vê | 404 | 403 da atividade¹ |
| `group_manager` efetivo | lista | 200 | vê | concede | 403 |
| Admin, BraCVAM | lista | 200 | vê | concede | concede se o cargo global edita a atividade, senão 403 |

¹ Sem concessão de editar a atividade: `require_activity_access` nega antes
de olhar o laboratório, com mensagem que cita só a atividade.

## Mensagens

- Execução invisível ou inexistente: `NotFoundError('Execução do laboratório
  não encontrada.')`. As rotas das issues #28 a #31 mapeiam para
  `404 not_found`.
- Gestor sem edição: `AuthorizationError('Só o próprio laboratório age na
  execução dele.')` → `403 forbidden`.

## Designação

`POST /processes/{id}/participants` (e aceite de convite) com
`participating_laboratory` para usuário que já tem essa designação ativa no
processo, por qualquer laboratório: `409`, código `duplicate`.

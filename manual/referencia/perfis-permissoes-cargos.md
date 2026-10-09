# Perfis, permissões e cargos

Dois mecanismos independentes. Perfis globais dão permissões na plataforma;
cargos dão acesso dentro de um processo. Como se combinam:
[Autorização](../explicacao/autorizacao.md).

## Perfis globais

| Perfil | `system_key` | Id | Permissões |
|---|---|---|---|
| Administrador | `administrator` | `00000000-0000-0000-0000-000000000009` | Todas as ativas, inclusive futuras |
| BraCVAM | `bracvam` | `00000000-0000-0000-0000-00000000000a` | Todas as ativas, inclusive futuras |
| Sem perfil | — | — | Nenhuma. Acesso só pelos cargos nos processos |

Perfis criados por `POST /rbac/profiles` têm só as permissões listadas neles.
Os perfis globais antigos (Grupo Gestor, Gerente do Estudo, Laboratório
Participante e outros) foram descontinuados; essas funções agora são cargos
por processo.

Além das permissões, Administrador e BraCVAM:

- veem todos os processos e todas as atividades;
- têm os cargos `admin` e `bracvam` em toda atividade, o que só dá edição onde
  o template lista esses cargos em `edit`.

Rotas exclusivas do perfil Administrador (`403 admin_only` para os demais):
reprocessar pré-avaliação e os logs administrativos.

## Permissões

| Código | Libera |
|---|---|
| `rbac.read` | Consultar perfis, permissões, acessos e histórico do RBAC |
| `rbac.profiles.manage` | Criar, alterar e desativar perfis |
| `rbac.assignments.manage` | Dar e tirar perfis de usuários |
| `users.read` | Listar contas |
| `users.manage` | Alterar e desativar contas |
| `institutional.read` | Consultar instituições, laboratórios, vínculos e histórico |
| `institutional.catalogs.manage` | Gerir instituições e laboratórios |
| `institutional.affiliations.manage` | Gerir vínculos de usuários |
| `process.participants.manage` | Designar e convidar qualquer cargo em qualquer processo |
| `ai_evaluations.read` | Consultar avaliações por IA |
| `ai_evaluations.manage` | Configurar, testar, publicar e associar avaliações |
| `triage.review` | Parecer por campo, decisão de triagem, retorno sobre a IA, arquivamento |
| `form_templates.manage` | Editar campos, nome e descrição de formulários |
| `collection_templates.manage` | Gerir os templates de coleta e baixar o arquivo-modelo; informar `collection_template_id` em `POST /processes` |

O catálogo de permissões só muda por migração.

## Cargos por processo

Um usuário tem um cargo no processo por designação ativa e
[efetiva](../explicacao/autorizacao.md#designacao-efetiva), ou por convite
aceito. `proponent` é dado a quem cria o processo.

| Cargo | Nome | Atividade que o designa | Observação |
|---|---|---|---|
| `proponent` | Proponente | — (criador) | Envia a proposta e responde ao retorno |
| `sponsor` | Patrocinador | `assign_sponsor` | |
| `group_manager` | Grupo Gestor | `assign_group_manager` | Gere participantes; dispensa e reabre execuções de laboratório |
| `sample_selection_group` | Grupo de Seleção de Amostras | `assign_sample_selection_group` | Único que vê substâncias, códigos e SDS |
| `lead_laboratory` | Laboratório líder | `assign_lead_laboratory` | Exige vínculo com o laboratório. Não dá acesso a execuções de laboratório |
| `participating_laboratory` | Laboratório participante | `assign_participating_laboratory` | Exige vínculo. No máximo uma designação ativa por usuário e processo |
| `statistician` | Estatístico | `assign_statistician` | |
| `collaborator` | Colaborador | `assign_collaborator` | |
| `adhoc_evaluator` | Avaliador ad hoc | `assign_adhoc_evaluator` | |
| `study_manager` | Gerente do Estudo | — | Só por designação direta |
| `peer_reviewer` | Revisor | — | Só por designação direta |
| `regulatory_observer` | Observador regulatório | — | Só por designação direta |

`admin` e `bracvam` também aparecem em `view`/`edit` dos templates, mas não
são designáveis: vêm do perfil global.

## Quem designa cada cargo

| Quem | Pode designar |
|---|---|
| Quem tem `process.participants.manage` (Admin, BraCVAM) | Qualquer cargo |
| `group_manager` efetivo do processo | Qualquer cargo |
| `proponent` efetivo do processo | `sponsor` e `group_manager` |

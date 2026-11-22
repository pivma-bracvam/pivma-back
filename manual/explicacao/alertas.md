# Alerts

Um alert avisa um usuário logado de que algo pede a atenção dele: uma
tarefa nova, uma decisão sobre a submissão, uma designação. A caixa de cada
pessoa fica em `GET /alerts`.

O alert não é o e-mail. O e-mail ([Notificações](notificacoes.md)) leva a
mensagem a quem está fora da plataforma e acompanha a entrega. O alert fica
na plataforma, guarda se o dono já leu e traz só o necessário para o front
escrever uma frase curta e levar a pessoa ao lugar certo. O mesmo
acontecimento pode gerar e-mail, alert, os dois ou nenhum.

## O que o alert traz

| Campo | Conteúdo |
|---|---|
| `kind` | Tipo do acontecimento (tabela abaixo) |
| `target` | `type` (`process`, `task` ou `sample_receipt`), `process_id` e `id` do objeto; `id` é `null` quando o destino é o processo |
| `params` | Identificadores e textos que o dono já vê no destino, com chaves fixas por tipo |
| `read_at` | `null` até o dono marcar como lido |
| `created_at` | Quando o acontecimento ocorreu |

O backend não guarda URL. O front traduz `target` na própria rota e monta o
texto a partir de `kind` e `params`.

## Tipos

Todos os tipos trazem `process_code` e `process_title` em `params`.

| `kind` | Quando | Quem recebe | `target.type` | Outros `params` |
|---|---|---|---|---|
| `task_opened` | Uma tarefa abre | Quem pode agir nela, pela mesma regra de `can_act` em `GET /tasks` | `task` | `activity_key`, `activity_name`, `run_number`, `due_date`; `laboratory_name` em execução por laboratório |
| `submission_status_changed` | A IA aprova a proposta; a triagem aprova ou rejeita | Proponentes do processo | `process` | `status`: `in_triage`, `approved` ou `rejected` |
| `structure_approved` | O BraCVAM homologa a estrutura | Participantes com designação ativa e efetiva, proponente incluído | `process` | |
| `process_withdrawn` | O proponente desiste na revisão do retorno | Perfil BraCVAM e participantes com designação ativa, fora o proponente | `process` | |
| `assignment_created` | Alguém designa o usuário | O designado | `process` | `role_key`, `laboratory_name` (`null` sem laboratório) |
| `assignment_revoked` | A designação é revogada | O designado | `process` | `role_key`, `laboratory_name` |
| `assignment_effectiveness_changed` | O vínculo com o laboratório acaba ou volta | O designado | `process` | `role_key`, `laboratory_name`, `effective` |
| `laboratory_run_completed` | Um laboratório conclui a execução | Grupo Gestor e Gerente do Estudo com designação efetiva | `process` | `activity_name`, `laboratory_name` |
| `laboratory_run_waived` | O Grupo Gestor dispensa um laboratório na fase | Designados por aquele laboratório | `process` | `phase_name`, `laboratory_name` |
| `sample_nonconformity_decided` | O Grupo de Seleção decide um problema de recebimento | Designados pelo laboratório do frasco, um alert por frasco | `sample_receipt` | `laboratory_name`, `blind_code`, `vial_status` |

A devolução da submissão, a chegada para triagem, o reenvio, a homologação
pendente, a reabertura de atividade e o problema no recebimento chegam como
`task_opened`, porque cada um abre uma tarefa. Use `activity_key` para
escrever o texto, por exemplo "Sua submissão voltou para ajustes" quando
vier `submission_return_review`.

## Regras

- Quem fez a ação não recebe o alert dela. A liberação feita pela
  pré-avaliação por IA não tem autor: o proponente recebe a devolução e a ida
  para a triagem.
- Conta desativada não recebe. Quem tem dois cargos que qualificam recebe um
  alert só.
- O alert é gravado na mesma transação da operação. Se a operação falhar,
  nenhum alert fica gravado. A configuração do e-mail não interfere.
- Concluir, cancelar ou reabrir a tarefa não muda o alert. Se uma colega
  conclui a triagem, o seu alert continua lido ou não lido como estava.
- Destinatários são calculados no momento do acontecimento. Quem ganha o
  cargo depois não recebe os alerts anteriores.
- Cada pessoa do BraCVAM recebe o alert de toda triagem, designação e
  homologação de todos os processos, cerca de onze por processo, porque o
  perfil é global.

## O que os `params` nunca trazem

Justificativa, parecer, resultado da IA, indicação de falha da IA, nome de
quem avaliou ou decidiu, nome químico, CAS, SDS, orientação do Grupo de
Seleção ou código do frasco novo. Um laboratório nunca recebe alert sobre
outro laboratório.

## O alert não dá acesso

Ao abrir o destino, a rota de sempre confere a permissão. Se a designação
foi revogada, a tarefa saiu do alcance do usuário ou o processo foi
excluído, a leitura responde `404`, e o alert continua na caixa. Mostre que
o item não está mais disponível.

## Ler e limpar

```bash
curl -s "$API/alerts?unread=true&per_page=20" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$API/alerts/$ALERT_ID/read" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$API/alerts/read-all" -H "Authorization: Bearer $TOKEN"
```

- A lista vem do mais recente para o mais antigo, no
  [envelope de listagem](../referencia/listagens-e-referencias.md), com
  `unread_count` no topo. O contador ignora o filtro e a página, então
  `per_page=1` basta para o selo de não lidos.
- Marcar de novo um alert lido responde `200` e mantém o `read_at`.
- `read-all` responde `{"updated": n}`.
- Alert de outra pessoa responde `404`, igual a um inexistente.
- Ler não grava evento na linha do tempo.

Não há aviso em tempo real: consulte a caixa quando o usuário navegar.

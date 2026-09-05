# Modelo de Dados: Submissão de Método Alternativo

RF007 não cria entidade nem tabela. Ele combina os registros já persistidos abaixo.

## Entidades reutilizadas

| Entidade | Uso no RF007 | Regras relevantes |
|---|---|---|
| `ProcessTemplate` / `ProcessTemplateVersion` | Seleciona a definição ativa e fixa a versão usada pela instância. | A criação falha se não houver versão publicada disponível. |
| `ProcessInstance` | Representa a submissão/método e armazena o `crCode` em `code`. | `code` é único no banco; status fica `SUBMISSION`. |
| `Assignment` | Representa o proponente local. | Um acesso RF007 exige `role_key=proponent`, `revoked_at IS NULL`, `deleted_at IS NULL` e usuário não excluído. |
| `ActivityInstance` / `ActivityRun` | Representam a atividade inicial `proposal_submission` e sua execução em elaboração. | RF007 não a conclui, nem desbloqueia triagem. |
| `FormTemplate` / `FormField` | Definem campos, ordem, tipo, opções e regras. | A definição da instância é a fonte de leitura e validação. |
| `FormInstance` | Liga o formulário à execução inicial. | Mantém `is_submitted=false` durante o rascunho RF007. |
| `FormValue` | Armazena um valor por campo do formulário. | O payload inteiro é validado antes de criar/alterar valores. |
| `AuditEvent` | Registra criação, designação e gravação de rascunho. | Autor, processo e execução permanecem ligados ao evento. |

## Relações

```text
ProcessTemplateVersion 1 ── * ProcessInstance(code = crCode)
ProcessInstance 1 ── * Assignment(role_key = proponent)
ProcessInstance 1 ── * ActivityInstance 1 ── * ActivityRun 1 ── * FormInstance
FormTemplate 1 ── * FormField
FormInstance 1 ── * FormValue * ── 1 FormField
ProcessInstance 1 ── * AuditEvent
```

## Regras de valores de rascunho

| Tipo persistido | Entrada aceita | Armazenamento | Regras adicionais |
|---|---|---|---|
| `text`, `textarea` | string ou `null` | `text_value` | Nenhuma regra textual nova é inferida se a definição não a trouxer. |
| `integer` | inteiro JSON, exceto booleano, ou `null` | `numeric_value` | Aplica `min` e `max` quando declarados. |
| `float` | número JSON, exceto booleano, ou `null` | `numeric_value` | Aplica `min` e `max` quando declarados. |
| `boolean` | booleano ou `null` | `boolean_value` | `false` é valor presente. |
| `date` | string ISO `YYYY-MM-DD` ou `null` | `date_value` | Data inválida falha. |
| `select` | valor configurado em `options` ou `null` | `json_value` | Deve coincidir com `options[*].value`. |
| `file_upload` | nenhum valor em RF007 | nenhum | Valor enviado falha; RF008 definirá upload e vínculo com `Artifact`. |

`null` representa limpeza de um valor parcial. A obrigatoriedade não é verificada ao salvar rascunho. O envio formal de RF014 decidirá a completude e o tratamento de obrigatórios.

## Estados e atomicidade

```text
criação bem-sucedida
  -> ProcessInstance(SUBMISSION)
  -> Assignment(proponent ativo)
  -> ActivityInstance(proposal_submission, IN_PROGRESS)
  -> ActivityRun(IN_PROGRESS)
  -> FormInstance(is_submitted=false)

PUT válido -> FormValues atualizados + FORM_DRAFT_SAVED
PUT inválido -> nenhuma alteração de FormValue e nenhum evento de sucesso
```

O motor já comita a criação depois de preparar os registros. Uma exceção anterior ao commit não torna a instância acessível. A gravação de rascunho deve conservar o mesmo limite transacional.

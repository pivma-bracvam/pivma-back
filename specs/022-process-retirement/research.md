# Pesquisa: Ciclo de Vida de Processos

## Critério de rascunho

**Decision**: Considerar rascunho descartável somente o processo sem `AuditEvent` de tipo `SUBMISSION_SUBMITTED`.

**Rationale**: `ProcessInstance.started_at` é preenchido já na instanciação e `SUBMISSION` volta a ocorrer após devolução para correção. O evento de submissão formal é criado em `submit_proposal_form` e preserva o marco necessário sem nova coluna ou migração.

**Alternatives considered**: Usar `status == SUBMISSION` permitiria apagar uma submissão devolvida. Usar `started_at` classificaria todo processo recém-criado como já iniciado no pipeline.

## Estados e persistência

**Decision**: Reutilizar `ProcessInstance.status` e `closed_at`; introduzir apenas os valores de status `CANCELLED` e `ARCHIVED` no código de domínio. Rascunhos nunca submetidos sofrem exclusão física em cascata; uma revisão devolvida pode ser encerrada como `CANCELLED` sem apagar histórico.

**Rationale**: As colunas são strings sem enum ou restrição de banco e os filhos já empregam `CANCELLED`. Os eventos guardam status anterior, ator e momento em `AuditEvent.context_data`; não é necessário campo ou tabela adicional. Rascunhos sem submissão não exigem retenção do agregado e seus anexos ocupam armazenamento local.

**Alternatives considered**: `DELETED` acrescentaria um estado sem valor de negócio. Manter exclusão lógica de rascunhos reteria linhas e anexos descartados. Criar campos de arquivamento e uma tabela de transições aumentaria a migração e a superfície sem requisito adicional.

## Comando HTTP e apoio ao front-end

**Decision**: Expor `DELETE /processes/{id}`, `PATCH /processes/{id}/withdrawal`, `PATCH /processes/{id}/cancellation` e `PATCH /processes/{id}/archive`, todos sem corpo de justificativa. As operações de estado devolvem `status` e `available_actions`; a exclusão física devolve `204 No Content`.

**Rationale**: Os verbos HTTP expressam a intenção e impedem que a interface envie estados arbitrários. Cancelamento, desistência e arquivamento usam a mesma transação de domínio, mas possuem autorização e pré-condições explícitas. Os códigos estáveis permitem à interface renderizar apenas comandos aplicáveis, enquanto o backend continua autoritativo.

**Alternatives considered**: Um endpoint RPC único misturaria exclusão, desistência e mudanças de estado, além de induzir justificativa obrigatória. Alterações diretas de `status` transfeririam a máquina de estados ao cliente.

## Autorização e visibilidade histórica

**Decision**: Reutilizar `is_active_effective_proponent` para excluir rascunho próprio ou desistir de revisão, e `triage.review` para cancelar, arquivar e solicitar `status=ARCHIVED`.

**Rationale**: O proponente efetivo já é resolvido pelo vínculo local; `triage.review` já representa a autoridade de decisão da etapa implementada. Nenhuma permissão nova é necessária.

**Alternatives considered**: Criar uma permissão específica de ciclo de vida ampliaria RBAC sem necessidade da issue. Usar apenas o perfil global permitiria ações a usuários sem competência de review. Expor arquivados em listagens padrão mistura trabalho operacional e histórico.

## Cancelamento em cascata e concorrência

**Decision**: Carregar o processo alvo com bloqueio de linha e validar a ação. `DELETE_DRAFT` remove o agregado e o diretório de anexos do rascunho; cancelamento atualiza processo, filhos pendentes e evento de auditoria na mesma transação. Marcar somente `Phase`, `ActivityInstance`, `ActivityRun`, `Task` e `EvaluationRun` ainda não terminais como `CANCELLED`; manter formulários, artefatos, decisões e itens concluídos inalterados.

**Rationale**: O bloqueio serializa comandos concorrentes sobre a mesma instância. A remoção do rascunho inclui as tabelas dependentes e `ATTACHMENTS_DIR/{process_id}/`, evitando linhas órfãs e arquivos sem referência. `FormInstance` não tem estado de ciclo de vida, e preservá-lo evita converter rascunhos em submissões. `EvaluationRun` pendente deve ser cancelada para que o worker reconheça a operação.

**Alternatives considered**: Manter exclusão lógica do agregado deixaria rascunhos e anexos descartados ocupando recursos. Reescrever itens concluídos de processo submetido destruiria o histórico. Uma transação por entidade permitiria estado parcial.

## Guardas para escrita e processamento assíncrono

**Decision**: Centralizar uma guarda de processo operacional nos serviços mutantes de formulário, submissão, triagem, tarefas e pré-avaliação; antes de rotear ou gravar resultado assíncrono, confirmar que o processo ainda existe e está em `AI_PRE_EVALUATION` quando aplicável.

**Rationale**: Algumas rotas atuais chegam ao motor sem uma verificação de terminalidade, e `_execute` da pré-avaliação verifica apenas a execução. A guarda no domínio cobre rotas atuais e chamadas futuras; a condição no worker impede conclusão tardia de avançar um cancelado.

**Alternatives considered**: Bloquear somente o endpoint de ciclo de vida não evita outras rotas nem callbacks em andamento. Cancelar o job sem conferir seu estado na conclusão ainda deixa uma corrida possível.

## Demonstração e seed

**Decision**: Criar uma página independente em `demos/process-retirement/`, registrada no catálogo, e um seed idempotente que produza um rascunho inicial, um processo ativo, um `CLOSED` e um caso inválido usando templates e usuários existentes.

**Rationale**: Atende ao `AGENTS.md` sem endpoint auxiliar ou dependência do núcleo. A própria demo usa login e os endpoints de processo reais.

**Alternatives considered**: Reutilizar dados genéricos torna os estados não determinísticos. Um endpoint de preparação violaria a regra de desacoplamento.

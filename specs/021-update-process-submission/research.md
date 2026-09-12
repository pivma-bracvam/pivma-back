# Research: 021 - Atualização de Instância de Submissão

**Date**: 2026-09-11

## Decisão 1: um endpoint da instância, não uma API nova de formulário

- **Decisão**: expor `PUT` e `PATCH /processes/{id}` com `title` e `values`.
- **Racional**: a alteração solicitada é da instância de submissão e reúne o
  título, que não pertence a `FormInstance`, com seus campos dinâmicos. A rota
  de rascunho por atividade já existente continua compatível para seu uso
  específico, mas não é estendida para alterar título ou versões.
- **Alternativas consideradas**: uma rota por campo, ou um recurso
  `submission` separado. Rejeitadas: multiplicariam contratos sem resolver
  uma necessidade de domínio distinta.

## Decisão 2: validar e persistir em um único serviço transacional

- **Decisão**: criar um serviço no motor de processo que carrega a execução
  atual, valida o payload inteiro com as regras de `FormField` já usadas no
  rascunho e somente então persiste título/valores/auditoria no mesmo commit.
- **Racional**: atende a atomicidade sem introduzir repositório ou camada de
  comando. `PUT` acrescenta a checagem de completude de todos os campos não
  arquivo; `PATCH` mantém os ausentes.
- **Alternativas consideradas**: chamar duas rotas existentes em sequência ou
  fazer commits separados. Rejeitadas: permitem estado parcialmente alterado.

## Decisão 3: bloquear após envio e reutilizar a run devolvida

- **Decisão**: permitir escrita somente no maior `ActivityRun.run_number` de
  `proposal_submission`, se seu `FormInstance.is_submitted` for falso. A
  devolução `NEEDS_REVISION` continua abrindo a próxima run pelo helper
  existente.
- **Racional**: a execução submetida já é concluída e imutável. O código já
  clona valores em uma nova `FormInstance` para ajustes, sem necessidade de
  reabrir ou editar a run anterior.
- **Alternativas consideradas**: liberar alteração após submissão ou criar
  versão em cada salvamento. Rejeitadas pela regra arquitetural expressa e por
  aumentarem risco/auditoria sem requisito.

## Decisão 4: snapshot sem tabela de versão

- **Decisão**: usar `ActivityRun.run_number` como versão. No envio, acrescentar
  `title` ao `Artifact` `proposal_dossier`, que já armazena valores e manifesto
  de anexos; usar `submitted_at` e o evento `REVISION_REQUESTED` para data e
  justificativa.
- **Racional**: cada reenvio já tem `FormInstance` e valores próprios. O único
  dado mutável que faltava no retrato era o título.
- **Alternativas consideradas**: tabela de snapshots ou JSON duplicado em uma
  nova entidade. Rejeitadas: duplicam estado que já está preservado por run.

## Decisão 5: preservar referência de anexo histórico

- **Decisão**: ao remover/substituir anexo na nova run, não soft-deletear o
  `Artifact` se houver referência a ele em `FormValue` de formulário submetido.
- **Racional**: a reabertura atual copia `file_attachment_id`; apagar o
  artefato antigo invalidaria o snapshot que a feature promete expor.
- **Alternativas consideradas**: copiar fisicamente o arquivo a cada run ou
  criar tabela de retenção. Rejeitadas: não são necessárias para conservar a
  referência existente.

## Decisão 6: autorização e leitura histórica

- **Decisão**: escrita exige proponente efetivo ou acesso de plataforma
  BraCVAM/Admin já reconhecido por `has_platform_wide_access`; leitura histórica
  aplica `process_visibility_clause` e devolve 404 fora do escopo.
- **Racional**: reutiliza a autorização contextual e não adiciona permissão ou
  papel.
- **Alternativas consideradas**: permissão nova de edição/histórico. Rejeitada:
  amplia RBAC sem necessidade identificada.

# Data Model: 021 - Atualização de Instância de Submissão

**Date**: 2026-09-11

Nenhuma tabela ou migração é necessária. A versão histórica é uma projeção
imutável das entidades já persistidas no envio formal.

```text
ProcessInstance (title mutável somente no rascunho atual)
  └── ActivityInstance [proposal_submission]
        ├── ActivityRun #1 [COMPLETED]
        │     └── FormInstance [is_submitted=true, submitted_at]
        │           └── FormValue*                 ┐
        │     └── Artifact [proposal_dossier]      ├─ versão #1 congelada
        │           metadata: title, values, attachments
        │     └── AuditEvent [SUBMISSION_SUBMITTED]┘
        └── ActivityRun #2 [IN_PROGRESS, se devolvida]
              └── FormInstance [is_submitted=false]
                    └── FormValue*                 ── rascunho editável

AuditEvent [REVISION_REQUESTED]
  context_data: new_run_number, justification
  liga a devolução da versão anterior à run nova.
```

## Entidades e regras

| Entidade | Papel nesta feature | Regra |
|---|---|---|
| `ProcessInstance` | título e estado do processo | `title` aceita 3–255 caracteres e só muda na atualização autorizada de rascunho; status não muda por PUT/PATCH. |
| `ActivityRun` | identificador de versão | `run_number` da atividade `proposal_submission` é a versão apresentada; não criar contador adicional. |
| `FormInstance` | limite de mutabilidade | a maior run é editável somente com `is_submitted=false`; uma submetida nunca é reaberta. |
| `FormValue` | dados dinâmicos | PUT substitui o conjunto de campos não arquivo; PATCH altera somente chaves enviadas; tipos/opções/limites vêm da definição associada. |
| `Artifact` | snapshot formal | `proposal_dossier.metadata_payload` passa a incluir `title`, valores e referências de anexos da mesma run. |
| `AuditEvent` | trilha | `SUBMISSION_UPDATED` registra ator, modo e nomes alterados; `REVISION_REQUESTED` fornece a justificativa da devolução. |

## Transições

| Situação | Escrita PUT/PATCH | Versão |
|---|---|---|
| Run atual em elaboração | permitida ao sujeito autorizado | nenhuma criada |
| Envio formal | não é PUT/PATCH; fluxo existente conclui a run | snapshot da run criado |
| Triagem pede revisão | fluxo existente cria run seguinte em elaboração | anterior permanece histórica |
| Processo em triagem, IA, fechado ou cancelado | recusada | nenhuma criada |

Anexos não entram no corpo PUT/PATCH. A referência de arquivo de uma run
submetida deve sobreviver a uma substituição na run posterior.

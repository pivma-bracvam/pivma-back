# Contrato HTTP: Composição do Roteiro (sem endpoint novo)

Nenhum endpoint é criado por esta spec (Constituição, Princípio II). Os três já
existentes abaixo passam a, juntos, permitir montar o roteiro de duas fases no cliente.
Nenhum deles muda de formato de resposta — o que muda é apenas o **conteúdo**
(`activity_type` novo dentro de um payload que já era livre) retornado por eles depois
que a versão 2 do template `validated_method_dossier` é publicada.

## 1. Estrutura declarada — `GET /processes/templates/{key}`

Já retorna `definition` como o payload YAML cru (`ProcessTemplateDetail.definition`).
Nenhuma alteração de schema Pydantic é necessária: o campo `activity_type` de cada
atividade passa a vir de graça, por já fazer parte do dicionário declarativo.

```json
{
  "id": "uuid",
  "key": "validated_method_dossier",
  "name": "Método Validado – Dossiê Submetido",
  "version_number": 2,
  "definition": {
    "phases": [
      {
        "key": "phase_1_submission_triage",
        "activities": [
          { "key": "proposal_submission", "activity_type": "form", "...": "..." },
          { "key": "triage_evaluation", "activity_type": "form", "...": "..." }
        ]
      },
      {
        "key": "phase_2_planning_preview",
        "name": "Fase 2: Planejamento (prévia)",
        "activities": [
          {
            "key": "planning_preview",
            "name": "Prévia do Planejamento",
            "activity_type": "placeholder",
            "dependencies": [
              { "required_activity_key": "triage_evaluation", "required_status": "COMPLETED" }
            ]
          }
        ]
      }
    ]
  }
}
```

Isso dá ao cliente a lista completa de fases/atividades e o tipo de cada uma,
independentemente de a instância já ter chegado lá.

## 2. Status macro — `GET /processes/{id}`

Sem alteração de schema. `status` transita normalmente entre `SUBMISSION → TRIAGE →
PLANNING` como já ocorre hoje; a Fase 2 de exemplo não introduz um novo valor de status
macro.

## 3. Status por atividade — `GET /tasks?process_id={id}`

Sem alteração de schema. A atividade `planning_preview`, como qualquer outra, produz
exatamente uma `Task` quando é ativada — a mesma convenção 1:1 já usada pela Fase 1. Antes
da triagem ser aprovada, ela simplesmente não aparece na lista (nenhuma `Task` existe
ainda); depois da aprovação, aparece com `status = "READY"`.

## Sequência para a demonstração

1. `GET /processes/templates/validated_method_dossier` → renderizar o roteiro completo
   (2 fases, 3 atividades), decorando cada nó com `activity_type`.
2. `POST /processes {template_key: "validated_method_dossier", title: "..."}` → cria a
   instância (versão 2, já a mais recente publicada).
3. Preencher e enviar `proposal_submission` (fluxo já existente, Spec 004/009).
4. `POST /processes/{id}/triage/decision {outcome: "APPROVED", ...}` (fluxo já existente,
   Spec 004/014).
5. `GET /tasks?process_id={id}` → a atividade `planning_preview` aparece com
   `status = "READY"`, tipo `placeholder`, comprovando que o roteiro avançou para "algo
   que não é formulário" sem nenhum endpoint novo.

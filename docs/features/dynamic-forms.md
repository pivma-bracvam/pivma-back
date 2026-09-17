# Formulários Dinâmicos e Versionamento de Templates

A submissão de propostas na PIVMA é baseada em formulários dinâmicos com schemas versionados, permitindo que o BraCVAM adapte campos e perguntas sem alterar o código do sistema.

---

## 🏗️ Estrutura de Templates de Processo

Cada processo instanciado referencia uma versão publicada de um template:
- `ProcessTemplate`: Define o tipo do método (ex: `pre_validated_method`, `scope_extension`).
- `ProcessTemplateVersion`: Versão imutável do template (`version_number`).
- `FormTemplate`: Formulário associado a uma atividade do roteiro (ex: `proposal_submission`).
- `FormField`: Campos individuais com validações e parametrização de IA.

---

## 📝 Ciclo de Vida do Rascunho (Draft)

Durante a etapa de `SUBMISSION`, o proponente pode preencher o formulário aos poucos:

### Atualização Integral (`PUT`)
Substitui todos os campos do formulário:
```http
PUT /processes/{id}/forms/proposal_submission
Content-Type: application/json

{
  "values": {
    "method_title": "Ensaio de Irritação Ocular em Modelo 3D",
    "proponent_organization": "Instituto de Biotecnologia",
    "intended_use": "Substituição do ensaio Draize em coelhos"
  }
}
```

### Atualização Parcial (`PATCH`)
Atualiza apenas campos pontuais sem afetar o restante:
```http
PATCH /processes/{id}/forms/proposal_submission
Content-Type: application/json

{
  "values": {
    "method_title": "Título Revisado com Diretriz OCDE 492"
  }
}
```

### Envio Formal (`POST .../submit`)
Valida a obrigatoriedade de todos os campos e transiciona o processo para `AI_PRE_EVALUATION` ou `TRIAGE`:
```http
POST /processes/{id}/forms/proposal_submission/submit
```
Após o envio formal, o rascunho é congelado e nenhuma edição adicional é permitida.

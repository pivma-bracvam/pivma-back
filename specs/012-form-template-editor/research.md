# Research: Editor e Customização de Templates de Formulários de Processo (Versão 1.1)

## Decisão 1: Endpoints para Customização de Templates de Formulários

### Contexto
Hoje existem os endpoints `GET /processes/templates` e `GET /processes/templates/{key}`. Falta a capacidade de persistir modificações nos formulários e campos associados a cada template de processo.

### Decisões Técnicas

1. **Rota Principal de Atualização do Formulário do Template**:
   - `PUT /processes/templates/{key}/forms/{form_key}`
   - **Payload**: Recebe o nome/descrição atualizados do formulário e a lista ordenada de definições de campos (`fields`).
   - **Permissão**: Restrito a usuários com perfis autorizados da equipe BraCVAM (`RBAC` administrativo / `admin` / perfil institucional correspondente).
   - **Comportamento**: Atualiza a entidade `FormTemplate` identificada por `form_key`, sincroniza os `FormField` associados (inserindo novos, atualizando existentes e marcando soft-delete nos removidos) e sincroniza o `definition_payload` da `ProcessTemplateVersion` publicada mais recente.

2. **Rota Complementar de Atualização Integral do ProcessTemplate (Opcional/Conveniência)**:
   - `PUT /processes/templates/{key}`
   - Permite atualizar metadados gerais do template de processo (`name`, `description`) e o `definition_payload` integral.

### Alternativas Consideradas
- *Endpoints granulares por campo (`POST /fields`, `PUT /fields/{id}`, `DELETE /fields/{id}`)*: Rejeitado porque no paradigma de Form Editor (especialmente para formulários com ordem, seções e dependências), salvar o conjunto estruturado do formulário de uma vez garante consistência atômica e simplifica o fluxo na interface web.

---

## Decisão 2: Agrupamento em Seções de Formulário

### Contexto
O usuário solicitou que a edição permita customizar "as sessões desse formulário, tipos, se é obrigatório, todo o kit basico de um form editor".

### Decisão Técnica
- Cada campo de formulário (`FormFieldDefinition`) suportará um atributo `section` (string, ex: `"Identificação da Proposta"`, `"Justificativa Mecanística"`, `"Protocolo do Estudo"`).
- Para retrocompatibilidade de banco sem migrações disruptivas, o atributo `section` é armazenado como metadado no modelo de dados (podendo integrar o `validation_rules` como `{"section": "..."}` ou como campo dedicado no schema Pydantic `FormFieldDefinition`).
- O editor visual agrupa os campos em blocos visuais retráteis (accordions/cards) baseados no valor de `section`, permitindo reordenar campos dentro de uma seção e criar novas seções dinamicamente.

---

## Decisão 3: Integração Simplificada de Avaliação por IA (Spec 010)

### Contexto
O usuário reforçou: *"Vamos manter a parte da IA simplificada (spec 010) vamos precisar de uma spec apenas para trabalhar com esse ponto, mas o restante já deve ser possivel executar agora"*.

### Decisão Técnica
- O editor de formulários mantém os 3 atributos da Spec 010 já incorporados nos esquemas:
  1. `ai_evaluation_enabled: bool` (toggle na interface para habilitar/desabilitar análise por IA);
  2. `ai_context_instructions: str | None` (área de texto para orientações contextuais de avaliação);
  3. `ai_validation_rules: dict | None` (regras simplificadas como `min_length`, palavras-chave).
- A esteira mock em 3 etapas da Feature 010 (`FormAIPipelineEngine`) consome exatamente esses atributos quando o formulário for instanciado e submetido.

---

## Decisão 4: Ciclo de Vida: Design-Time vs Run-Time e Isolamento Histórico

### Contexto
O usuário definiu: *"toda vez que o proponente for criar uma instancia aquele processos ele dê de cara com esse formulário especifico que foi editado"*, destacando que *"só os proponentes instanciam os processos para serem avaliados"*.

### Decisão Técnica
- **Design-Time (BraCVAM)**: O usuário BraCVAM edita o template do formulário através de `PUT /processes/templates/{key}/forms/{form_key}`. A versão mais recente do template armazena o novo esquema.
- **Run-Time (Proponente)**: Quando um proponente faz `POST /processes`, a função `instantiate_process` lê a versão vigente de `ProcessTemplateVersion` e os `FormTemplate.fields` ativos, gerando uma `ProcessInstance` com os `FormInstance` correspondentes.
- **Imutabilidade Histórica**: Processos instanciados antes da alteração mantêm suas referências de `ActivityRun` e `FormInstance` intactas, preservando valores passados sem sofrer impactos das alterações futuras do template.

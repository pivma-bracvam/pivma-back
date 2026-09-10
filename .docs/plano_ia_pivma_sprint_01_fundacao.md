# Plano de Implementação IA PIVMA --- Sprint 01: Fundação da Avaliação Configurável

## Objetivo

Criar a base arquitetural para substituir a avaliação fixa atual por uma
avaliação orientada por configuração, mantendo o pipeline existente,
contratos canônicos, logs e auditoria.

## Escopo

-   Manter o FormAIPipelineEngine como orquestrador principal.
-   Substituir avaliações específicas por capacidades genéricas.
-   Criar conceito de definição de avaliação.
-   Separar configuração da execução.
-   Preparar fluxo de primeira avaliação automática obrigatória.

## Entregas

### Modelo conceitual de avaliação

Definir que uma avaliação possui:

-   objetivo;
-   critérios;
-   evidências esperadas;
-   severidade;
-   comportamento esperado quando houver falha;
-   versão da configuração.

A configuração deve representar conhecimento regulatório e não detalhes
técnicos de IA.

### Pipeline

Evoluir o pipeline atual para executar avaliações compostas.

O fluxo esperado:

Submissão do formulário

↓

Identificação de campos avaliáveis

↓

Carregamento da configuração de avaliação

↓

Execução da avaliação

↓

Geração do relatório

↓

Persistência do resultado para auditoria

## Regras de negócio

Implementar:

-   Toda primeira submissão passa obrigatoriamente pela avaliação IA.
-   O resultado da IA deve ser armazenado.
-   O proponente recebe o resultado preliminar.
-   Uma reprovação inicial não encerra o processo definitivamente.
-   O proponente pode contestar a avaliação e solicitar análise humana.

## Mock inicial

Manter:

-   leitura de documentos simulada;
-   análise de imagens simulada;
-   OCR simulado;
-   inferência simulada.

O objetivo desta fase é validar fluxo e experiência.

## Critérios de conclusão

-   Pipeline executa uma avaliação configurável.
-   Resultado fica disponível para consulta.
-   Logs continuam funcionando.
-   Submissão inicial dispara avaliação automaticamente.
-   Contestação do proponente possui fluxo definido.

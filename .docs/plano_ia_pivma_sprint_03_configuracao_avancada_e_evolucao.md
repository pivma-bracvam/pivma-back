# Plano de Implementação IA PIVMA --- Sprint 03: Configuração Avançada e Evolução da IA

## Objetivo

Criar uma experiência simples para usuários configurarem avaliações
complexas sem necessidade de conhecimento técnico de IA.

## Escopo

Criar assistente de configuração de avaliações.

## Experiência administrativa

O administrador informa:

### O que deve ser avaliado?

Exemplos:

-   resumo metodológico;
-   documento;
-   POP;
-   anexos;
-   conjunto de campos.

### Qual é o objetivo?

Exemplo:

"Verificar se o POP permite reprodução adequada do método."

### Quais critérios devem ser considerados?

Exemplo:

-   possui identificação;
-   possui versão;
-   possui metodologia;
-   possui referências;
-   possui critérios de aceitação.

### Qual evidência é necessária?

Exemplo:

"A conclusão deve estar baseada no conteúdo do documento e não apenas no
nome do arquivo."

## Tipos de avaliação

Suportar conceitualmente:

-   presença de informação;
-   conformidade;
-   qualidade;
-   comparação entre informações;
-   consistência entre campos.

## Avaliação de documentos e imagens

Continuar inicialmente com mocks.

Preparar interfaces para futuras capacidades:

-   extração de texto;
-   OCR;
-   análise visual;
-   comparação multimodal.

## Biblioteca de avaliações

Permitir avaliações reutilizáveis:

-   validação de POP;
-   validação de resumo;
-   validação documental;
-   requisitos normativos.

## Governança

Adicionar:

-   versionamento de avaliações;
-   testes antes da publicação;
-   comparação entre versões;
-   métricas de concordância humana.

## Critérios de conclusão

-   Administrador cria avaliações sem escrever prompts.
-   Avaliações podem ser reutilizadas.
-   Alterações geram novas versões.
-   O sistema está preparado para integração futura com modelos reais.

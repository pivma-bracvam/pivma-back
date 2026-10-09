# Observações e pendências

Este documento reúne divergências entre fontes, ambiguidades e perguntas para a equipe, como pedem a constituição do Spec Kit e o [índice da documentação](README.md). Nenhum item altera as fontes oficiais.

## Recuperação de senha (issue #45, Spec 039)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a issue #45 admite "imprimir o token em logs em ambiente local/desenvolvimento".
- **Conflito**: a Spec 036 proíbe o link bruto em logs. O backend de e-mail falso e o Mailpit do compose, ambos da Spec 036, já entregam o link em testes e em desenvolvimento.
- **Decisão**: o token nunca vai para log, em nenhum ambiente. Em desenvolvimento, o link é lido no Mailpit (`http://localhost:8025`).
- **Validação**: confirmada pelo usuário em 2026-10-02. Registrada em `specs/039-password-reset/spec.md` (Clarifications, FR-004 e Assumptions) e citada na descrição da PR.

## Template de coleta de dados (issue #26)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a issue #26 pede o construtor de colunas, os parâmetros de experimentos e réplicas e o arquivo-modelo em CSV e Excel. O [guia do protótipo](guia-prototipo.md) (seção 4) descreve um template mais amplo: oito tipos de coluna, colunas derivadas, colunas reservadas, flag de ensaios fracassados e configuração dentro do processo pelo Estatístico. O Plano de Trabalho não tem RF específico; o mais próximo é o RF036.
- **Conflito**: a issue e o protótipo divergem em tipos, colunas e momento de configuração. Nenhum documento define quando a "Etapa 3 começa" nem como o template chega ao processo.
- **Decisão**: o protótipo está descontinuado e não vale como fonte. Valem as decisões abaixo, que complementam a issue #26 e têm precedência sobre o guia do protótipo.
- **Validação**: confirmada pelo usuário em 2026-10-09.

### DECISÕES VIGENTES

Regra geral: implementar com a menor complexidade que cumpra os critérios de aceite da issue. Não adicionar recurso fora desta lista.

1. **Modelo de dados**: tabelas novas e próprias, sem reaproveitar `FormTemplate` nem `FormField`. Duas tabelas: `collection_templates` (nome, descrição, `min_experiments`, `min_replicates`) e `collection_template_columns` (rótulo, chave técnica, tipo, obrigatoriedade, opções, posição). Ambas usam o `AuditMixin`.
2. **Tipos de coluna**: exatamente `text`, `integer`, `decimal`, `date` e `select`. `select` exige opções não vazias; os outros tipos rejeitam opções.
3. **Colunas reservadas**: toda saída (CSV e Excel) começa com três colunas fixas: `codigo_amostra`, `experimento` e `replica`. São constantes no código e não ficam no banco. Essas chaves são reservadas e a criação de coluna com elas é rejeitada, como acontece com chave duplicada. Laboratório, operador e datas não entram, porque o laboratório vem da autenticação.
4. **Fora de escopo**: colunas derivadas (cálculo entre colunas) e a flag "permitir ensaios fracassados" com o `Status de Execução`. Nenhuma fonte define a fórmula nem a semântica, e a #30 é quem as consumiria. Não implementar nesta issue.
5. **Etapa 3**: é a fase `phase_3_validation_execution` dos templates de processo (Spec 040). Ela começa quando a atividade `sample_definition` do processo fica `COMPLETED`.
6. **Catálogo global**: o template de coleta não pertence a um processo. Ele é criado antes e escolhido na criação do processo.
    - `POST /processes` ganha o campo opcional `collection_template_id`. É opcional para não quebrar processos e testes existentes.
    - `process_instances` ganha uma coluna anulável com o vínculo. Não existe rota para trocar o template depois.
    - **Travamento estrutural**: o template fica travado se algum processo vinculado a ele tem `sample_definition` concluída. O estado se calcula por consulta, sem flag armazenada. Um template travado continua selecionável por processos novos.
    - **Gestão do catálogo**: permissão nova, nos moldes de `form_templates.manage`, concedida a Admin e BraCVAM.
7. **Protótipo**: descontinuado. Não usar o guia como evidência.
8. **Biblioteca Excel**: `openpyxl`. Ela lê e escreve `.xlsx`, e a #30 precisa dos dois. Na leitura da #30, usar `read_only=True`.
9. **Réplicas**: `min_experiments` e `min_replicates` são mínimos, inteiros maiores ou iguais a 1.
10. **Registro de decisões**: este arquivo guarda as decisões e divergências de issues futuras, no formato das seções acima.

Decisões menores, também vigentes:

- **Posição da coluna**: inteiro maior ou igual a 1, único dentro do template. Sem posição informada, a coluna vai para o fim. Reordenar fica fora de escopo.
- **Chave técnica**: deve casar com `^[a-z][a-z0-9_]{0,63}$` e ser única dentro do template.
- **CSV gerado**: UTF-8 com BOM e separador `;`. O arquivo-modelo traz só o cabeçalho, em CSV e em Excel, sem validação de lista no Excel.
- **Vínculo na criação do processo**: só quem tem a permissão de gestão do catálogo informa `collection_template_id` em `POST /processes`. Os demais recebem 403 ao enviar o campo; sem o campo, a criação segue aberta (usuário, 2026-10-09).
- **Leitura do catálogo**: listar, consultar e baixar o arquivo-modelo exigem a mesma permissão. O acesso do laboratório ao arquivo-modelo do seu processo fica para a #30 (usuário, 2026-10-09).
- **Cabeçalho do arquivo-modelo**: as colunas vêm identificadas pela chave técnica. O rótulo aparece só na consulta do template (usuário, 2026-10-09).
- **Origem confiável em processos**: as seis rotas de escrita de `routers/processes.py` (criar, substituir, alterar, excluir e arquivar processo, e alterar a definição de formulário do template de processo) e as duas de formulário de atividade em `routers/forms.py` (salvar rascunho e enviar) passam a exigir `Origin` confiável quando a sessão vem do cookie, como manda a constituição (III). A revisão desta entrega apontou a falta em `POST /processes` (usuário, 2026-10-09).

### GLOSSÁRIO

O termo "template" tem três sentidos no repositório. Use sempre a forma qualificada em código, rotas, testes e textos:

- **Template de processo** (`ProcessTemplate`): fases e atividades de um processo.
- **Formulário** (`FormTemplate`): campos preenchidos numa atividade.
- **Template de coleta** (`CollectionTemplate`): estrutura da planilha de resultados brutos. O arquivo que o laboratório baixa é o **arquivo-modelo**.

Nomes no código: tabelas `collection_templates` e `collection_template_columns`; rota `/collection-templates`.

### PENDÊNCIAS

- Colunas derivadas e semântica de "ensaios fracassados" (decisão 4): decidir quando a #30 ou outra issue as exigir.
- A #30 passa a exigir que o processo tenha template de coleta vinculado. Um processo criado por proponente sem a permissão de gestão do catálogo fica sem vínculo, e nenhuma rota o vincula depois. A #30 precisa decidir como esse processo recebe o template. A decisão bloqueia a jornada do proponente na #30 e deve sair antes de ela começar.

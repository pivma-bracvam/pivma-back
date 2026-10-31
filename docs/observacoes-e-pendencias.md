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
5. **Etapa 3**: é a fase `phase_3_validation_execution` dos templates de processo (Spec 040). Ela começa quando a atividade `sample_definition` do processo fica `COMPLETED`. A issue #27 mudou o início da Etapa 3 e a trava do template; ver a seção "Homologação da estrutura".
6. **Catálogo global**: o template de coleta não pertence a um processo. Ele é criado antes e escolhido na criação do processo.
    - `POST /processes` ganha o campo opcional `collection_template_id`. É opcional para não quebrar processos e testes existentes.
    - `process_instances` ganha uma coluna anulável com o vínculo. Não existe rota para trocar o template depois.
    - **Travamento estrutural**: o template fica travado se algum processo vinculado a ele tem `sample_definition` concluída. Substituído pela issue #27: o template trava quando a Etapa 3 de algum processo vinculado começa. O estado se calcula por consulta, sem flag armazenada. Um template travado continua selecionável por processos novos.
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

## Homologação da estrutura (issue #27)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a issue #27 lista três insumos para auditar: papéis, amostras e plano estatístico. A atualização de 2026-10-04 retirou a Análise Estatística (#25) do escopo e pediu que se definisse se a homologação exige plano estatístico.
- **Conflito**: a homologação pode reabrir a definição das amostras, e a decisão 5 da #26 trava o template de coleta pela conclusão dessas amostras. Com a reabertura, o template destravaria no meio do estudo.
- **Decisão**: as decisões abaixo complementam a issue #27 e substituem a decisão 5 da #26 no início da Etapa 3 e na trava do template.
- **Validação**: confirmada pelo usuário em 2026-10-14. A revisão do PR #76, em 2026-10-16, mudou as decisões 1, 2 e 5. Registrada em `specs/042-structure-approval/spec.md` (Clarifications).

### DECISÕES VIGENTES

1. **Plano estatístico**: a homologação o exige. A Etapa 2 ganha a atividade `statistical_plan`, do Estatístico, que abre quando a atribuição do estatístico conclui. O Estatístico envia um formulário com o plano em anexo (obrigatório) e um resumo (opcional). O plano é um ponto da homologação e pode ser reprovado como os outros; a nova execução traz um formulário novo e guarda o anterior. O plano não tem avaliação por IA nesta entrega. O envio de formulário só gera o Dossiê de Submissão, a pré-avaliação por IA e a triagem na submissão da proposta.
2. **Pendências obrigatórias**: as dez atividades da Etapa 2 bloqueiam a aprovação, inclusive Colaboradores, Comitê ad hoc e o plano estatístico.
3. **Início da Etapa 3**: nos processos criados depois desta feature, a Etapa 3 começa na aprovação da homologação. Os processos antigos mantêm o início na conclusão das amostras.
4. **Trava do template de coleta**: o template trava quando a Etapa 3 de algum processo vinculado começa. Para os processos antigos o momento não muda.
5. **Reexecução de atribuição de cargo**: a atividade reaberta não conclui sozinha. Quem gere o cargo declara que terminou a correção por `POST /processes/{id}/participants/roles/{role_key}/complete`, aceito quando o cargo tem ao menos uma designação ativa e nenhum convite pendente, e recusado para quem tem conflito de interesse vigente. Assim a ordem entre designar a pessoa nova e revogar a antiga não importa. Na primeira execução, a atividade continua concluindo na designação ou na revogação.
6. **Convite adicional após a conclusão**: criar um convite depois que a atribuição de cargo concluiu não reabre a atividade nem bloqueia, por si só, a homologação. O BraCVAM aprova com base nas designações ativas e na consistência das amostras no momento da decisão. Em atribuições abertas ou reabertas, os convites pendentes continuam impedindo a conclusão. Decisão confirmada pelo usuário em 2026-10-14.

### PENDÊNCIAS

- Avaliação por IA do plano estatístico: fora desta entrega. Se entrar, não pode travar o envio nem mexer na triagem.

## Terminologia dos tipos e código da submissão (documento do BraCVAM, Spec 043)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: o documento "Sugestões de ajustes no sistema PiVMA", que o BraCVAM enviou em outubro de 2026, seção 1 (tipos de submissão) e seção 2.1, item 3 (código da submissão). Não há issue no GitHub.
- **Conflito**: os nomes atuais dos tipos vêm da Spec 015 e misturam termos em inglês. O BraCVAM pede a terminologia do OECD GD 34, outra ordem e a remoção da Prova de Conceito. `GET /processes/templates` ordena por nome, e a ordem alfabética dos nomes novos não coincide com a pedida. O Plano de Trabalho (seção 3.2, "crCode") só exige um código único, e o código atual termina em 16 caracteres aleatórios que ninguém consegue citar.
- **Decisão**: as decisões abaixo. Os demais pedidos do documento (título único, explicação do envio para análise e Formulário Preliminar em toda submissão) seguem em discussão na equipe.
- **Validação**: confirmada pelo usuário em 2026-10-24.

### DECISÕES VIGENTES

1. **Nomes e descrições**: os tipos passam a ser, nesta ordem:

    | Ordem | Chave | Nome | Descrição |
    |---|---|---|---|
    | 1 | `pre_validated_method` | Método Novo | Método em desenvolvimento ou já desenvolvido, cujo processo de validação ainda não foi executado. |
    | 2 | `validated_method_dossier` | Método Novo – Dossiê Completo | Método novo já desenvolvido, com protocolo estabelecido e processo de validação concluído, cujo dossiê está disponível para avaliação por pares. |
    | 3 | `scope_extension` | Extensão do Domínio de Aplicação | Proposta de ampliação do domínio de aplicação de um método já validado, incluindo uma nova finalidade de uso ou aplicação regulatória. |
    | 4 | `me_too_validation` | Método Similar | Método de ensaio estrutural e funcionalmente semelhante a um método de referência já validado e aceito, podendo ser candidato a um processo de validação baseado em padrões de desempenho (performance standards). |

    A expressão "Fitness for Purpose Validation" sai da descrição da Extensão.
2. **Chaves técnicas**: as chaves dos tipos e dos formulários continuam as mesmas. O frontend e os testes dependem delas. Esconder as chaves da tela cabe ao frontend.
3. **Ordem**: `GET /processes/templates` devolve os tipos na ordem da tabela. O template de processo passa a declarar a própria ordem de exibição, e a lista deixa de ordenar pelo nome. A ordem é obrigatória no YAML: o bootstrap recusa o arquivo sem ela (usuário, 2026-10-24).
4. **Prova de Conceito**: sai por completo. Removemos o YAML, o formulário `submission_proof_of_concept_v1`, os testes que cobrem só esse tipo e as menções no manual e no `templates_data/README.md`. A Spec 015 fica como está, por ser histórico. O mapeamento do Formulário Preliminar continua em `specs/015-first-deploy-baseline/data-model.md` e no histórico do git, caso a equipe aceite o pedido de levá-lo a toda submissão.
5. **Código da submissão**: o formato passa a `VAL-<ano>-<sequencial>`, como `VAL-2026-0001`. A sequência recomeça em 1 a cada ano e usa no mínimo quatro dígitos, com zeros à esquerda; acima de 9999, o número só cresce (`VAL-2026-10000`). O ano é o da criação no horário de Brasília (`America/Sao_Paulo`), onde a plataforma terá a maior parte dos usuários. Duas criações simultâneas nunca recebem o mesmo número, e uma criação que falha não consome número.
6. **Dados existentes**: o banco do preview só tem dados de teste, e a produção vai começar vazia. Não migramos os códigos antigos nem tratamos processos abertos da Prova de Conceito.

### PENDÊNCIAS

- Título único, explicação do botão "Enviar para análise" e Formulário Preliminar em toda submissão: aguardam decisão da equipe.
- O frontend ainda mostra as chaves técnicas (`PRE_VALIDATED_METHOD`) nos cartões dos tipos.

## Bootstrap e o editor de formulários (revisão da Spec 043)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a Spec 012 (Q4) diz que a definição salva pelo editor passa a valer para os novos processos. O `entrypoint.sh` roda `python -m pivma.bootstrap_system` a cada início do contêiner da API, e esse comando sincroniza os formulários a partir dos YAMLs de `src/pivma/templates_data/`.
- **Conflito**: a cada deploy ou reinício da API, o bootstrap desfaz o que o BraCVAM salvou no editor. Uma reprodução em 2026-10-24, editando dois formulários de `pre_validated_method` e rodando o bootstrap de novo, mostrou que:
  - o nome do formulário volta ao do YAML e a versão volta de 2 para 1;
  - o rótulo, a obrigatoriedade e a configuração de IA dos campos do YAML voltam aos valores do YAML;
  - um campo que o editor removeu volta a aparecer;
  - um campo que o editor criou continua na tabela de campos, mas some da definição da versão do template, e as duas fontes passam a divergir.
- **Opções**:
  1. O bootstrap só cria o que falta e nunca altera formulário existente. Uma mudança de YAML num formulário que já existe, como os nomes novos da Spec 043, deixa de chegar ao banco e passa a precisar de migração.
  2. O bootstrap preserva o formulário que o editor alterou. O editor já soma 1 à versão do formulário a cada gravação: quando a versão no banco é maior que a do YAML, o bootstrap deixa o formulário e a entrada dele na definição da versão como estão. Para impor uma mudança de YAML a um formulário editado, a equipe sobe a `version` no YAML. Os demais formulários seguem o YAML como hoje.
  3. Os YAMLs são a única fonte, e o editor fica restrito a ambientes de teste. Contraria as Specs 012 e 013.
- **Decisão**: opção 2. O bootstrap compara a versão de cada formulário no banco com a do YAML:
  - versão do banco maior: o bootstrap não toca no formulário, nos campos dele nem na entrada dele na definição da versão do template;
  - versão igual ou menor: o YAML prevalece. O bootstrap aplica o YAML, desativa os campos que não estão nele e retira esses campos das avaliações de IA associadas, como o editor faz ao remover um campo.

  Para impor uma mudança de YAML a um formulário editado, a equipe sobe a `version` do formulário no YAML acima da versão do banco. A edição do BraCVAM nesse formulário se perde.
- **Validação**: confirmada pelo usuário em 2026-10-24.

## Processos de tipo aposentado (Spec 044)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: o `GET /processes` do preview respondeu 500 em 2026-10-31. O banco tem 3 processos `OPEN` de `proof_of_concept`, tipo que o bootstrap aposentou em 2026-10-26.
- **Conflito**: a decisão 6 da Spec 043 dispensou o tratamento desses processos. A equipe não previu que um deles derrubaria a lista inteira de quem o enxerga.
- **Decisão**: a lista e o detalhe mostram o tipo aposentado dos processos existentes, sem mudar o formato da resposta. O tipo continua fora de `GET /processes/templates` e não aceita processos novos.
- **Validação**: confirmada pelo usuário em 2026-10-31.

### PENDÊNCIAS

- Destino dos 3 processos do preview: a equipe decide se os cancela. O formulário `submission_proof_of_concept_v1` também saiu, e ninguém testou se esses processos ainda avançam.

## Conteúdo dos formulários de submissão (formulário do BraCVAM para as opções 1, 2 e 3)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a equipe repassou em 2026-10-24 a [pasta do BraCVAM no Google Drive](https://drive.google.com/drive/folders/1i3RI2f-P7SvJh9abQIqbAq4BFHYzo4ki), com dois arquivos:
  - "etapas sistema NPAI gerenciamento validação.pptx" lista cinco opções de submissão: (1) método novo com validação por executar; (2) método já validado com nova aplicação; (3) método já validado com novo sistema teste; (4) método novo com validação concluída e dossiê pronto; (5) ideia de método ainda a desenvolver.
  - "Formulario_BraCVAM SISTEMA - Novos métodos, métodos já validados ou novos desfechos - opções 1,2 e 3.docx" traz o formulário de submissão dessas três opções, com 48 perguntas em 13 seções: proponente, método, necessidade e impacto, fundamentação científica, sistema teste, protocolo, controle de qualidade, desempenho, capacidade preditiva, limitações, propriedade intelectual, interesse regulatório e anexos.
- **Conflito**: os formulários de submissão em `src/pivma/templates_data/` são provisórios. A Spec 015 os definiu "só para haver algo na tela":
  - Método Novo, Extensão do Domínio de Aplicação e Método Similar têm um campo, "Título do método" (SC-007 da Spec 015);
  - o Dossiê Completo tem o título e um campo de terminologia com avaliação de IA, feito para demonstrar a IA;
  - o único formulário que reproduzia um formulário real do BraCVAM era o Formulário Preliminar da Prova de Conceito, com 81 campos, que a Spec 043 removeu junto com o tipo.

  As cinco opções da apresentação não coincidem com os quatro tipos do sistema. A opção 5 corresponde à Prova de Conceito, removida. A opção 3 não tem tipo equivalente, e o Método Similar não aparece na apresentação. A numeração da apresentação também difere da ordem de exibição: o Dossiê Completo é a opção 4 lá e o 2º tipo na tela.
- **Decisão**: nenhuma. O formulário fica fora da Spec 043.
- **Validação**: pendente.

### PENDÊNCIAS

1. **Tipos atendidos**: o formulário das opções 1, 2 e 3 vale para quais tipos? A opção 1 é o Método Novo e a opção 2 é a Extensão do Domínio de Aplicação. A opção 3 cabe na Extensão, no Método Similar ou em um tipo novo? E o Método Similar usa qual formulário?
2. **Dossiê Completo**: o BraCVAM ainda não enviou o formulário da opção 4. Até lá, o tipo continua com o formulário provisório?
3. **Quem cadastra os campos**: a equipe escreve o formulário no YAML, versionado e coberto por testes, ou o BraCVAM o monta pelo editor? Pela regra do bootstrap (seção anterior), um formulário editado no banco só volta a seguir o YAML quando a `version` do YAML passar a do banco.
4. **Formulário Preliminar em toda submissão**: este formulário substitui esse pedido, que segue pendente na seção da Spec 043?
5. **Forma dos campos**, que o documento não define:
   - perguntas compostas, como a 8 ("Possui um Patrocinador? Quem? Qual a verba prevista?"), viram um campo ou vários?
   - perguntas de resposta fechada, como a 2 (natureza da instituição) e a 11 (tipo de método), viram listas de opções? Quais opções?
   - quais perguntas são obrigatórias?
   - a pergunta 10 ("Nome oficial do método e sigla") substitui o campo "Título do método"? A pendência do título único depende disso.
   - a seção 1 repete dados do cadastro do proponente (e-mail, instituição). O formulário os pede de novo ou os traz do cadastro?
   - os anexos da seção 13 ficam em um campo de arquivo ou em um por tipo de documento (POP, artigos, relatórios, planilhas)?
6. **Avaliação de IA**: quais campos a IA avalia na triagem, e com quais critérios? A apresentação diz que os critérios ainda precisam ser definidos.

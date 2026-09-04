# Pesquisa: Submissão de Método Alternativo

## Identificação única

**Decisão**: gerar o `crCode` como `VAL-{ano}-{token aleatório de 16 hexadecimais}` e manter `ProcessInstance.code` como seu único armazenamento.

**Justificativa**: `generate_process_code` usa `COUNT(*) + 1`; duas transações podem calcular o mesmo valor. `process_instances.code` já possui `UNIQUE`, mas a geração aleatória evita a colisão normal de concorrência e a restrição mantém a garantia no banco. O formato cabe no `String(32)` atual e preserva o prefixo aceito pelos testes.

**Alternativas consideradas**:

- Sequência PostgreSQL por ano: exige migração, ciclo de reinício anual e estado novo sem requisito oficial.
- Lock transacional e contador: serializa criações e mantém o problema de contar dados históricos.
- Identificador paralelo: contraria a decisão da spec de usar `ProcessInstance.code` como `crCode`.

## Autorização contextual

**Decisão**: usar uma consulta específica para proponente ativo e eficaz.

**Justificativa**: `participant_read_scope` considera qualquer designação e gestores. RF007 permite somente o proponente durante a elaboração. O novo predicado precisa verificar processo, usuário, papel `proponent`, ausência de revogação, ausência de exclusão lógica e usuário não excluído.

**Alternativas consideradas**:

- Reutilizar `participant_read_scope`: concederia leitura a papéis proibidos pela spec.
- Basear o acesso em perfil global: ignora a participação no processo e viola RF004.
- Criar RBAC novo: RF007 não precisa de uma permissão global adicional.

## Validação do formulário

**Decisão**: validar e normalizar o payload inteiro contra `FormField` antes de alterar `FormValue`.

**Justificativa**: a gravação atual ignora chaves desconhecidas e faz coerções como `bool("false")`. A validação prévia preserva o estado anterior diante de erro e permite ao frontend associar cada erro à chave do campo.

**Alternativas consideradas**:

- Deixar Pydantic modelar os campos científicos: os campos são dinâmicos e pertencem a `FormTemplate`/`FormField`.
- Validar enquanto grava: permitiria persistência parcial quando um campo posterior falhasse.
- Exigir obrigatórios no rascunho: contraria a clarificação que reserva completude a RF014.

## Campos de documento

**Decisão**: `file_upload` não recebe valor no rascunho RF007; retornar erro por campo se o cliente o enviar.

**Justificativa**: o template atual contém `study_protocol_file`, mas RF008 está fora do escopo. Gravar uma string, caminho ou UUID como se fosse arquivo criaria uma anexação simulada. A ausência do campo não bloqueia o rascunho parcial.

**Alternativas consideradas**:

- Criar `Artifact`: implementa RF008 sem autorização de escopo.
- Aceitar nome de arquivo em `text_value`: simula anexo e não fornece gestão documental.
- Remover o campo da definição persistida: altera configuração administrativa fora do RF007.

## Contrato para frontend

**Decisão**: manter `POST /processes`, `GET /processes/{id}`, `GET/PUT /processes/{id}/activities/{activity_key}/form` e `GET /processes`.

**Justificativa**: estes endpoints já refletem a infraestrutura reutilizada. O contrato inclui `form_instance_id`, metadados de campos e valores no `GET`, para que o frontend renderize a definição sem nomes de campos codificados. O `PUT` aceita valores parciais e devolve erros por chave.

**Alternativas consideradas**:

- `POST /submissions`: duplicaria criação e exigiria um router/schema paralelo.
- Endpoint por campo: aumenta chamadas, auditoria e regras de atomicidade sem benefício para RF007.

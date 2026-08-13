# Research: Cadastro Seguro de Usuários

> **Nota (2026-08-12)**: após a redução de escopo desta versão (ver `spec.md`, Clarifications,
> Session 2026-08-12), as seções sobre blocklist de senhas e sobre inspeção de formato de
> credencial na migração descrevem pesquisa histórica que não corresponde mais à implementação.
> Ficam preservadas como registro da investigação original, não como decisão vigente.

## 1. Proteção de senha

**PROPOSTA aprovada nesta feature — Decision**: Adicionar `argon2-cffi >=25.1,<26`, sob revisão de
cada atualização pela pessoa solicitante da feature, e usar `argon2.PasswordHasher` com Argon2id e o
perfil explícito `RFC_9106_LOW_MEMORY`. Executar o hashing síncrono em worker thread para não
bloquear o event loop. Armazenar somente o valor codificado completo em `password_hash`.

**Rationale**: O valor codificado inclui algoritmo, versão, salt e custos. O perfil usa 64 MiB,
três iterações e paralelismo quatro, supera o piso Argon2id da OWASP e não possui o limite de
72 bytes do bcrypt. A versão 25.1 declara suporte a Python 3.14.

**Alternatives considered**:

- `bcrypt`: rejeitado pelo limite de entrada incompatível com 128 caracteres Unicode.
- Passlib ou `pwdlib`: rejeitados por adicionarem abstração sem necessidade nesta feature.
- PBKDF2: reservado para eventual requisito FIPS, ausente das fontes.
- SHA-256 rápido ou criptografia reversível: inadequados para armazenamento de senha.

**Sources**:

- [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
- [argon2-cffi how-to](https://argon2-cffi.readthedocs.io/en/stable/howto.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

## 2. Validação exata da senha

**PROPOSTA — Decision**: Contar code points Python, aceitar de 8 a 128, rejeitar qualquer caractere para o
qual `str.isspace()` seja verdadeiro e não aplicar trim, NFC, NFKC ou outra transformação.
Comparar a senha completa e exata com a blocklist antes do Argon2id.

**Rationale**: Implementa a decisão explícita da spec. Argon2 recebe `str` em UTF-8 e processa
integralmente senhas Unicode nesse intervalo.

**Alternatives considered**:

- Normalização NFC: recomendada pelo NIST, mas contradiz a decisão aprovada de não transformar.
- Aceitar espaços: recomendado para frases-senha, mas contradiz a spec.
- Regras de composição: rejeitadas pela spec e pelas recomendações atuais.

## 3. Blocklist local e versionada

**CONFIRMADO nesta feature — Fonte**: A blocklist será derivada da lista pública
`xato-net-10-million-passwords-100000.txt` do SecLists, fixada pelo commit registrado nos
metadados. A aquisição registra data, checksums e referência aos termos. O HIBP não oferece um
artefato oficial contendo apenas as 100.000 maiores ocorrências; a equipe aprovou a troca de fonte
para evitar baixar o corpus completo.

**PROPOSTA aprovada nesta feature — Decision**: Derivar, fora do runtime, os hashes SHA-1 das
100.000 entradas na ordem publicada pela fonte. Empacotar `hashes.sha1` e `metadata.json` em
`src/pivma/resources/password_blocklist/`. Consultar somente o SHA-1 uppercase da senha inteira
codificada em UTF-8; SHA-1 serve apenas como identificador do corpus, nunca como hash persistido.

`hashes.sha1` deve conter um hash hexadecimal uppercase por linha, sem duplicatas e em ordem
lexicográfica. `metadata.json` deve registrar versão local, fonte, URL, data de obtenção, checksum
da fonte, critério de seleção, quantidade, algoritmo, encoding e checksum do artefato.

**Rationale**: O desenho funciona sem rede, não guarda senhas em claro, não adiciona biblioteca e
permite verificar origem, integridade e versão. Os metadados registram também a ferramenta de
derivação e a referência aos termos vigentes na aquisição. O carregamento valida formato,
quantidade e checksum uma vez e falha fechado se o recurso estiver ausente ou corrompido.

Um match retorna HTTP 422 com `{"detail": "Invalid password"}`. Resposta, exceção e log não
podem incluir senha, SHA-1, Argon2id, fragmentos ou o motivo da blocklist. Recurso ausente ou
corrompido constitui falha operacional, não erro 422 do usuário: não há lista vazia nem fallback de
rede; a recuperação exige restaurar o artefato íntegro e reiniciar ou reimplantar a aplicação.

**Alternatives considered**:

- API HIBP: rejeitada por criar dependência externa no cadastro e não fornecer ranking global.
- Corpus HIBP completo: rejeitado pelo volume exigido para derivar apenas 100.000 entradas.
- Lista em texto claro ou tabela: rejeitada por exposição e complexidade.
- Pacote de terceiros ou `zxcvbn`: rejeitado por dependência sem necessidade.

**Sources**:

- [NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html)
- [HIBP API e corpus Pwned Passwords](https://haveibeenpwned.com/API/V3)
- [HIBP Pwned Passwords Downloader](https://github.com/HaveIBeenPwned/PwnedPasswordsDownloader)
- [SecLists](https://github.com/danielmiessler/SecLists)

## 4. Unicidade case-insensitive e concorrência

**PROPOSTA — Decision**: Preservar a caixa nas colunas e impor unicidade global com dois índices
únicos por expressão: `lower(username)` e `lower(email)`, sem predicado. Consultas prévias usam as
mesmas expressões e abrangem usuários excluídos logicamente.

**Rationale**: A verificação prévia mantém mensagens e precedência previsíveis, mas não fecha a
corrida entre consulta e inserção. Os índices tornam o banco a autoridade final e garantem que
somente um pedido concorrente seja criado.

**Alternatives considered**:

- Converter e armazenar lowercase: rejeitado porque a spec manda preservar a caixa.
- `citext`: rejeitado por exigir extensão e mudar a semântica da coluna sem necessidade.
- Apenas consulta prévia ou trava em processo: rejeitadas por não garantirem concorrência.
- Colunas canônicas adicionais: rejeitadas por duplicar estado derivável.
- Índices parciais: rejeitados porque liberariam identificadores após exclusão lógica e violariam
  FR-023.

**Sources**:

- [PostgreSQL: Indexes on Expressions](https://www.postgresql.org/docs/current/indexes-expressional.html)

## 5. Tradução de conflitos e transações

**PROPOSTA — Decision**: Fazer verificação prévia de username antes de e-mail. Após inserir, capturar somente
a violação dos índices esperados; executar `rollback()`, repetir a consulta determinística e
retornar o HTTP 409 correspondente. Propagar violações não reconhecidas.

**Rationale**: SQLAlchemy exige rollback explícito após falha de flush/commit. A nova consulta
preserva a precedência de username quando ambos conflitam e evita classificar todo
`IntegrityError` como duplicidade.

**Alternatives considered**:

- Interpretar somente texto da exceção: frágil e dependente do driver.
- Retornar um conflito genérico: quebraria o contrato atual.
- Capturar todo `IntegrityError`: esconderia falhas não relacionadas.

**Source**:

- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)

## 6. Dados legados e nome da coluna

**PROPOSTA — Decision**: Executar preflight antes de qualquer mutação: abortar se houver colisões de
identificadores ou qualquer credencial que não seja um Argon2id codificado válido. Se o preflight
passar, renomear `password` para `password_hash` e criar os índices globais; não transformar,
reproteger nem invalidar credenciais.

**Rationale**: Implementa FR-022 e impede que texto simples receba um nome de hash. A feature não
dispõe de fluxo aprovado para converter ou invalidar credenciais. A validação deve reconhecer a
estrutura codificada e o tipo Argon2id, não apenas um prefixo, e nunca incluir o valor no erro.

**Alternatives considered**:

- Proteger texto legado na migração: rejeitado por FR-022.
- Invalidar todas as senhas existentes: exigiria recuperação de senha, fora do escopo.
- Aceitar apenas o prefixo `$argon2id$`: rejeitado porque o prefixo não comprova formato válido.

## 7. Testes e empacotamento

**PROPOSTA — Decision**: Cobrir validações com testes de schema, segurança com testes unitários reais,
persistência e contratos com PostgreSQL descartável, corrida com sessões independentes e migração
com sucesso sobre hashes válidos e aborto atômico sobre credencial não Argon2id. Verificar payload
422 sanitizado, falha fechada e que wheel e sdist incluem a blocklist e seus metadados.

**Rationale**: Cada camada prova uma responsabilidade distinta sem mockar a garantia do banco ou o
formato Argon2id. Hashes exatos não são comparados porque o salt deve variar.

**Alternatives considered**:

- Somente testes da rota: insuficientes para migração, pacote e concorrência.
- Perfil Argon2 barato em todos os testes: rejeitado por mascarar a configuração real; stubs podem
  acelerar testes de rota, mantendo testes próprios com o perfil de produção.

## 8. Benchmark e aprovação

**CONFIRMADO na spec**: Não há limite numérico pré-fixado. O benchmark usa exatamente dois
cadastros válidos e distintos em concorrência no container, registra ambiente, parâmetros,
latências, duração total e pico de memória e exige aprovação explícita do responsável técnico.

**PROPOSTA — Decision**: Manter `RFC_9106_LOW_MEMORY` sem fallback automático. Resultado não
aprovado interrompe a aceitação e exige revisão do plano.

**Rationale**: Duas operações Argon2id podem sobrepor consumo de memória. A decisão mede esse custo
sem inventar uma meta ausente das fontes.

**Alternatives considered**:

- Redução automática: rejeitada pela spec.
- Limite numérico inventado no plano: rejeitado por falta de evidência.
- Benchmark isolado de uma chamada: insuficiente para SC-011.

## 9. Falhas internas e auditoria inicial

**CONFIRMADO na spec**: Falhas inesperadas de hashing, `flush` ou `commit` retornam HTTP 500
genérico após rollback, sem criação parcial, detalhes internos ou segredos. No cadastro público,
somente `created_at` recebe valor; os demais campos de auditoria permanecem nulos.

**PROPOSTA — Decision**: Testar separadamente os três pontos de falha e inspecionar resposta e
persistência. Não capturar violações de integridade desconhecidas como conflito de unicidade.

**Rationale**: Os testes separados comprovam FR-026 e evitam que um tratamento amplo de exceções
oculte falhas de banco ou exponha dados internos.

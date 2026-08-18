# Gestão de Usuários: backlog técnico

## Escopo e autoridade

Este documento organiza as diretrizes técnicas de backend e infraestrutura para o Módulo de Gestão de Usuários. Elas orientam a implementação, desde que permaneçam compatíveis com o [Plano de Trabalho da Fase II](../plano-de-trabalho-fase-ii.md) e com decisões formais posteriores da equipe.

O Plano de Trabalho continua sendo a fonte dos requisitos funcionais RF001–RF006 e dos requisitos transversais aplicáveis. Este backlog não é uma `spec.md`: cada item deve ser decomposto e aprovado pelo fluxo Spec Kit antes de qualquer implementação.

O documento-fonte que originou estas diretrizes ainda não está versionado no repositório. Esta normalização registra somente os itens comunicados à equipe; detalhes não registrados ficam explícitos como pendência de especificação.

Em caso de conflito entre uma diretriz técnica e o Plano, registre a divergência em [observações e pendências](../observacoes-e-pendencias.md) e solicite validação. Não escolha uma fonte silenciosamente.

## Classificação

| Classe | Uso neste documento |
|---|---|
| **Requisito oficial** | Comportamento exigido pelo Plano de Trabalho. |
| **Decisão técnica** | Direção de backend e infraestrutura que deve orientar a solução. |
| **Detalhe a especificar** | Critério necessário para implementar ou testar uma decisão. |
| **Adiado** | Item registrado, mas que não deve bloquear o núcleo do módulo. |

## Rastreabilidade com o Plano de Trabalho

| Requisito | Backlog técnico relacionado |
|---|---|
| RF001 — Cadastro e autenticação | Cadastro, autenticação web, gerenciamento de sessão e proteção dos fluxos de conta. |
| RF002 — Gestão de perfis de acesso | RBAC, perfis, permissões e administração de usuários. |
| RF003 — Vinculação institucional | Modelo e regras para instituição e laboratório do usuário. |
| RF004 — Controle de acesso | Policies e dependências FastAPI que considerem perfil, instituição e participação no processo. |
| RF005 — Designação de participantes | Atribuição de participantes a cada processo de validação. |
| RF006 — Declaração de conflito de interesse | Registro, consulta e efeito do conflito de interesse em designações e acesso. |

RF034 exige logs e auditoria. RF044 reforça o isolamento de dados por laboratório durante etapas restritas. Ambos devem orientar as decisões de autorização e rastreabilidade deste módulo.

## Diretrizes e backlog

### Autenticação e sessão

**Requisito oficial:** RF001 exige cadastro e autenticação.

**Decisões técnicas:**

- A autenticação web transporta JWTs por cookies.
- A sessão deve usar `access_token` de curta duração e `refresh_token` persistido para renovação e revogação.
- A solução deve incluir proteção CSRF compatível com autenticação por cookies.

**Estado atual confirmado:** a implementação existente emite um JWT de até oito horas em cookie `HttpOnly`, `Secure` e `SameSite=Strict`. Ela não deve ser interpretada como implementação completa do modelo com refresh token.

**Detalhes a especificar:** duração e claims dos tokens, formato do refresh token, rotação, limite de sessões, revogação, logout, expiração, atributos definitivos dos cookies, mecanismo CSRF e respostas de erro.

### RBAC e autorização contextual

**Requisitos oficiais:** RF002 e RF004; RF005 depende dessas regras para designações.

**Decisões técnicas:** modelar RBAC e aplicar policies e dependências FastAPI no backend. A autorização não pode depender apenas de controles da interface.

**Detalhes a especificar:** lista canônica de perfis, permissões por ação, relação entre papel global e participação no processo, tratamento de usuários vinculados a mais de uma instituição ou laboratório e matriz de acesso aos dados restritos.

### Administração de usuários

**Requisitos oficiais:** RF001–RF005, conforme a operação exercida.

**Decisão técnica:** disponibilizar operações de consulta, atualização e inativação para a gestão administrativa de usuários. A definição de rotas e contratos de API pertence à spec da feature.

**Detalhes a especificar:** quais perfis podem administrar contas, quais campos cada ator pode alterar, como funciona a inativação, quais dados podem ser expostos em listagens e como cada alteração é auditada.

### Vínculo institucional, designação e conflito de interesse

**Requisitos oficiais:** RF003, RF005 e RF006.

**Decisão técnica:** tratar vínculos institucionais e designações como dados de autorização, não como simples campos de perfil. O conflito de interesse deve afetar a elegibilidade e o acesso conforme regras aprovadas.

**Detalhes a especificar:** cardinalidade dos vínculos, ciclo de vida de uma designação, validações antes de designar, efeito de um conflito declarado e histórico necessário para auditoria.

### Auditoria

**Requisito oficial:** RF034.

**Decisão técnica:** registrar eventos relevantes de autenticação, administração de usuários, autorização, vínculos, designações e conflitos de interesse.

**Detalhes a especificar:** eventos obrigatórios, dados anteriores e posteriores, retenção, imutabilidade e autorização para consulta dos registros.

### Recuperação de conta, confirmação de e-mail e 2FA

**Decisões técnicas:** o backlog inclui recuperação de senha, confirmação de e-mail e autenticação em dois fatores.

**Detalhes a especificar:** prioridade, canais, expiração, limites de tentativa, recuperação de segundo fator, requisitos por perfil e critérios de aceite. Cada capacidade deve ser uma feature separada do Spec Kit.

### Mensageria

**Requisitos oficiais relacionados:** RF011 e RF033 exigem notificações assíncronas em outros fluxos do produto.

**Adiado:** integrações de mensageria e provedores específicos, incluindo e-mail e canais de mensagem, não devem bloquear RBAC, autorização contextual e o núcleo de Gestão de Usuários. A escolha de provedor, credenciais, filas, retentativas e observabilidade depende de especificação posterior.

## Ordem sugerida para especificação

1. RBAC e policies de autorização.
2. Administração de usuários e vínculo institucional.
3. Designação por processo e conflito de interesse.
4. Auditoria dos eventos desses fluxos.
5. Evolução da sessão com refresh token e CSRF.
6. Recuperação de conta, confirmação de e-mail e 2FA.
7. Mensageria.

Cada spec deve referenciar esta página, os RFs aplicáveis e os critérios de segurança, autorização, auditoria e testes que se aplicarem ao seu risco.

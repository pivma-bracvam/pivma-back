# Benchmark: Cadastro Seguro de Usuários

> **Nota (2026-08-12)**: este benchmark deixou de ser um gate formal de aceite desta feature (SC-011
> removido; ver `spec.md`, Clarifications, Session 2026-08-12). A medição abaixo permanece como
> registro histórico do ambiente em que foi coletada; pode ser revisitada se houver indício de
> latência excessiva em uso real.

## Execução de 2026-08-12

**Estado**: evidência do ambiente atual aprovada em 2026-08-12 pela pessoa solicitante da feature.

### Ambiente

- imagem da API: `pivma_api`, identificador
  `sha256:2ede6b5c7533a3ac11aa4c30e0832154307b77a1cfa4de89d463ec7ebb392e45`;
- base da imagem: `python:3.14-slim`;
- plataforma do container: `Linux 6.12.76-linuxkit aarch64`, glibc 2.41;
- Python no container: 3.14.7;
- PostgreSQL: imagem `pgvector/pgvector:pg17`, em container separado;
- limite de memória visível ao container: 7,75 GiB;
- aplicação iniciada após `alembic upgrade head`, com a blocklist empacotada e validada.

### Perfil Argon2id

- perfil: `RFC_9106_LOW_MEMORY`;
- memória por operação: 65.536 KiB;
- iterações: 3;
- paralelismo: 4;
- salt: 16 bytes;
- hash: 32 bytes;
- fallback ou redução automática: não utilizado.

### Procedimento

1. Confirmou-se que `users` continha zero linhas.
2. Dois workers foram sincronizados por uma barreira e enviaram exatamente dois
   `POST /users` simultâneos, com usernames, e-mails e senhas válidos e distintos.
3. A duração foi medida por relógio monotônico no cliente. O pico de memória foi lido em
   `VmHWM` do processo Uvicorn antes e depois dos pedidos.
4. Após os pedidos, conferiram-se a contagem de linhas e apenas o prefixo e o comprimento dos
   valores persistidos, sem registrar as senhas nem os hashes completos.

### Resultados

| Pedido | HTTP | Latência | Persistência pública |
|---|---:|---:|---|
| 1 | 201 | 166,753 ms | id, username e e-mail retornados |
| 2 | 201 | 166,228 ms | id, username e e-mail retornados |

- duração conjunta: 166,915 ms;
- usuários criados: 2;
- credenciais persistidas como Argon2id: 2 de 2;
- comprimento de cada valor codificado: 97 caracteres;
- `VmHWM` antes dos pedidos: 114.684 kB;
- `VmHWM` após os pedidos: 246.856 kB;
- aumento observado do pico: 132.172 kB, aproximadamente 129,07 MiB;
- memória corrente do container após a execução: 90,25 MiB;
- logs da API: exatamente dois `POST /users`, ambos com HTTP 201.

O `VmHWM` representa o maior RSS do processo desde sua inicialização. A diferença entre as duas
leituras isola o aumento observado durante este benchmark, mas não constitui uma garantia para
outras cargas ou limites de container.

### Aprovação

- responsável: pessoa solicitante da feature;
- decisão: aprova o registro destas medições como evidência do ambiente atual da feature;
- data da decisão: 2026-08-12.

Esta aprovação não define limite aceitável de latência ou memória para produção. A equipe deve
revisar esses limites com o responsável técnico antes de usar as medições como critério operacional
de produção. O perfil `RFC_9106_LOW_MEMORY` permanece inalterado.

# Jornadas do recebimento de amostras

Fonte: jornadas e Lista de Ações enviadas pelo usuário em 2026-10-04. A
descrição completa de cada jornada (passos, o que o ator espera ver e o que
não deve ver) está na docstring do teste. Todas ficam em
`tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`.

Personas: **Thiago**, analista do laboratório participante; **Ricardo**, do
Grupo de Seleção de Amostras.

| Jornada do usuário | Teste | Requisitos |
|---|---|---|
| Jornada 1: o recebimento perfeito | `test_jornada_1_recebimento_perfeito` | FR-017 a FR-020, FR-024 a FR-026, FR-044, FR-045 |
| Jornada 2: o recebimento com desvio | `test_jornada_2_recebimento_com_desvio` | FR-026 a FR-028, FR-038, FR-044 |
| Jornada 3: proteção contra falhas humanas | `test_jornada_3_protecao_contra_falhas_humanas` | FR-020, FR-021, FR-044 |
| Jornada 4: a perspectiva de retaguarda | `test_jornada_4_retaguarda_do_grupo_de_selecao` | FR-029 a FR-034, FR-037, FR-039, FR-043, FR-047 a FR-049 |
| Jornada 4, desfecho para o laboratório: o parecer chega a Thiago | `test_jornada_5_laboratorio_recebe_a_orientacao` | FR-033, FR-037, FR-047 a FR-049 |
| Lista de Ações 1: privacidade e isolamento | `test_privacidade_e_isolamento_do_laboratorio` | FR-018, FR-019, FR-040, FR-046 |
| Lista de Ações 2: preenchimento e validações | Jornada 3 e `tests/api/routers/test_sample_receipt_validation.py` | FR-020, FR-021 |
| Lista de Ações 3: registro conforme | Jornada 1 | FR-024, FR-025 |
| Lista de Ações 4: registro de inconformidade | Jornadas 2 e 4 e `tests/integration/notifications/test_sample_nonconformity_email.py` | FR-027 a FR-030, FR-043, FR-044 |

## Diferenças em relação ao texto original

| Trecho da jornada | Como ficou | Por quê |
|---|---|---|
| Jornada 4: "notificação prioritária surge na sua central" | Tarefa "Resolver problemas no recebimento de amostras", e-mail e o texto `alert` em cada inconformidade | Não existe central de notificações; decisão do usuário em 2026-10-04 |
| Jornada 4: "novo frasco reserva com o mesmo código cego" | O frasco reserva recebe código novo, ligado ao anterior só para o Grupo de Seleção | Decisão 3 da issue #71, confirmada pelo usuário |
| Jornada 1: "lote liberado para os ensaios da Etapa 3" | A mensagem e a conclusão da tarefa dizem isso; ainda não há atividade de ensaio depois do recebimento | Fora do escopo das issues #28, #71 e #72 |
| Lista de Ações 1: "fornecedor original" | Não há campo de fornecedor; a regra vale para nome, CAS, SDS e classificação de referência | O cadastro não guarda fornecedor |
| Jornada 4: "emite um parecer técnico orientador" | Campo opcional `lab_guidance` na decisão, que o laboratório lê no frasco e recebe por e-mail; a justificativa continua só do Grupo | Decisão do usuário em 2026-10-04 |
| Jornada 2: "o sistema apresenta um aviso antes de finalizar" | Pré-verificação `POST .../vials/{code}/check`, sem gravar nada | Decisão do usuário em 2026-10-04 |

Os desvios de cada jornada (cada campo inválido, cada perfil negado,
concorrência) têm testes focados em `tests/api/routers/test_sample_*` e
`tests/api/routers/test_samples_*`.

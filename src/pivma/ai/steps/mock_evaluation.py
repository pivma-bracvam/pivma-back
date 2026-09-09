import time

from pivma.ai.contracts import PipelineContext, StepResult


class MockEvaluationStep:
    """Etapa 2: Validação de conformidade simulada (*mock*)."""

    def execute(self, context: PipelineContext) -> StepResult:
        start_time = time.perf_counter()

        sanitized_value = context.data.get("sanitized_context", "")

        # Simulação realista de latência e análise
        issues = []
        if not sanitized_value:
            issues.append("Campo obrigatório ou sem conteúdo para análise técnica.")
        else:
            issues.append("A justificativa técnica não apresenta dados comparativos de citotoxicidade prévia.")
            issues.append("Ausência de detalhamento quanto aos controles metodológicos (positivos e negativos) aplicados.")

        token_count = context.data.get("token_estimate", 10)
        simulated_cost = round(token_count * 0.00003 + 0.0005, 6)

        # Pequena latência simulada determinística
        time.sleep(0.01)

        context.data["issues"] = issues

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return StepResult(
            step_order=2,
            step_name="mock_evaluation",
            status="SUCCESS",
            duration_ms=duration_ms,
            simulated_cost=simulated_cost,
            input_payload={
                "field_key": context.field_key,
                "sanitized_context": sanitized_value,
                "validation_rules": context.validation_rules,
            },
            output_payload={
                "issues_found": issues,
                "rule_check_status": "NON_COMPLIANT",
            },
        )

import time

from pivma.ai.contracts import PipelineContext, StepResult


class ContextExtractionStep:
    """Etapa 1: Extração e higienização do contexto e valor do campo."""

    def execute(self, context: PipelineContext) -> StepResult:
        start_time = time.perf_counter()

        raw_value = context.submitted_value
        if raw_value is None:
            sanitized = ""
        elif isinstance(raw_value, str):
            sanitized = raw_value.strip()
        elif isinstance(raw_value, dict) and "filename" in raw_value:
            # Para anexos/arquivos, extrair metadados e não binário bruto
            sanitized = f"[Arquivo: {raw_value.get('filename')}]"
        else:
            sanitized = str(raw_value)

        # Estimativa simples de tokens e custo
        word_count = len(sanitized.split()) if sanitized else 0
        token_estimate = max(1, int(word_count * 1.3))
        simulated_cost = round(token_estimate * 0.00001, 6)

        context.data["sanitized_context"] = sanitized
        context.data["token_estimate"] = token_estimate

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if duration_ms == 0.0:
            duration_ms = 1.0  # Garantir medição estritamente positiva

        return StepResult(
            step_order=1,
            step_name="context_extraction",
            status="SUCCESS",
            duration_ms=duration_ms,
            simulated_cost=simulated_cost,
            input_payload={
                "field_key": context.field_key,
                "field_label": context.field_label,
                "submitted_value": str(raw_value),
                "instructions": context.instructions,
            },
            output_payload={
                "sanitized_value": sanitized,
                "token_count_estimate": token_estimate,
            },
        )

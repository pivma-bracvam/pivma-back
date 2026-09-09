import time

from pivma.ai.contracts import AIEvaluationVerdict, PipelineContext, StepResult


class VerdictSynthesisStep:
    """Etapa 3: Consolidação do veredito canônico negativo por padrão."""

    def execute(self, context: PipelineContext) -> StepResult:
        start_time = time.perf_counter()

        issues = context.data.get("issues", [])
        if not issues:
            issues = ["Pendências técnicas preliminares identificadas no preenchimento."]

        recommendations = [
            "Incluir referências bibliográficas de estudos de viabilidade com metodologias correlatas.",
            "Descrever explicitamente os critérios de aceitação e limites de detecção do ensaio.",
        ]

        verdict = AIEvaluationVerdict(
            field_key=context.field_key,
            status="REPROVED",
            confidence_score=0.88,
            issues=issues,
            recommendations=recommendations,
        )

        context.data["verdict"] = verdict

        simulated_cost = 0.0003
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if duration_ms == 0.0:
            duration_ms = 1.0

        return StepResult(
            step_order=3,
            step_name="verdict_synthesis",
            status="SUCCESS",
            duration_ms=duration_ms,
            simulated_cost=simulated_cost,
            input_payload={
                "field_key": context.field_key,
                "issues_count": len(issues),
            },
            output_payload={
                "verdict": verdict.model_dump(mode="json"),
            },
        )

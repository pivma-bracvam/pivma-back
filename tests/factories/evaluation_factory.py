import factory

from pivma.core.database.models import (
    EvaluationCriterion,
    EvaluationDefinition,
    EvaluationReference,
    EvaluationVersion,
)


class EvaluationDefinitionFactory(factory.Factory):
    class Meta:
        model = EvaluationDefinition

    name = factory.Sequence(lambda n: f'Avaliação {n}')
    slug = factory.Sequence(lambda n: f'avaliacao-{n}')
    description = None
    mode = 'simple'


class EvaluationVersionFactory(factory.Factory):
    class Meta:
        model = EvaluationVersion

    class Params:
        definition = None

    @factory.lazy_attribute
    def definition_id(self):
        if self.definition is None:
            raise ValueError('definition must be a persisted definition')
        return self.definition.id

    version_number = 1
    objective = 'Verificar se o conteúdo está adequado.'
    status = 'draft'
    references = None
    test_run_count = 0


class EvaluationCriterionFactory(factory.Factory):
    class Meta:
        model = EvaluationCriterion

    class Params:
        version = None

    @factory.lazy_attribute
    def version_id(self):
        if self.version is None:
            raise ValueError('version must be a persisted version')
        return self.version.id

    statement = factory.Sequence(lambda n: f'Critério {n}')
    check_type = 'conformity'
    order_index = factory.Sequence(int)
    polarity = 'positive'
    required_evidence = None
    severity = 'medium'
    on_missing_info = 'indeterminate'
    recommendation_hint = None


class EvaluationReferenceFactory(factory.Factory):
    class Meta:
        model = EvaluationReference

    identifier = factory.Sequence(lambda n: f'NORM-{n}')
    label = factory.Sequence(lambda n: f'Norma {n}')
    version_label = '2026'
    reference_date = None

from uuid import uuid4

import factory

from pivma.core.database.models import EvaluationRun, EvaluationRunItem


class EvaluationRunFactory(factory.Factory):
    class Meta:
        model = EvaluationRun

    class Params:
        process = None
        activity_run = None
        form_instance = None

    @factory.lazy_attribute
    def process_instance_id(self):
        if self.process is None:
            raise ValueError('process must be a persisted process instance')
        return self.process.id

    @factory.lazy_attribute
    def activity_run_id(self):
        if self.activity_run is None:
            raise ValueError('activity_run must be a persisted activity run')
        return self.activity_run.id

    @factory.lazy_attribute
    def form_instance_id(self):
        if self.form_instance is None:
            raise ValueError('form_instance must be a persisted form instance')
        return self.form_instance.id

    correlation_id = factory.LazyFunction(uuid4)
    status = 'in_progress'


class EvaluationRunItemFactory(factory.Factory):
    class Meta:
        model = EvaluationRunItem

    class Params:
        run = None

    @factory.lazy_attribute
    def run_id(self):
        if self.run is None:
            raise ValueError('run must be a persisted evaluation run')
        return self.run.id

    criterion_statement = factory.Sequence(lambda n: f'Critério {n}')
    check_type = 'conformity'
    polarity = 'positive'
    severity = 'medium'
    conclusion = 'non_compliant'
    is_alert = True
    model_layer = 'fast'

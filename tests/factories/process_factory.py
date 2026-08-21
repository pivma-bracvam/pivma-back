import factory

from pivma.core.database.models import (
    FormField,
    FormTemplate,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)


class ProcessTemplateFactory(factory.Factory):
    class Meta:
        model = ProcessTemplate

    key = factory.Sequence(lambda n: f'template_{n}')
    name = factory.Sequence(lambda n: f'Template {n}')
    description = 'Pipeline de teste'
    is_active = True


class ProcessTemplateVersionFactory(factory.Factory):
    class Meta:
        model = ProcessTemplateVersion

    class Params:
        template = None

    @factory.lazy_attribute
    def template_id(self):
        if self.template is None:
            raise ValueError('template must be provided')
        return self.template.id

    version_number = 1
    definition_payload = factory.LazyFunction(dict)
    is_published = True


class FormTemplateFactory(factory.Factory):
    class Meta:
        model = FormTemplate

    key = factory.Sequence(lambda n: f'form_template_{n}')
    name = factory.Sequence(lambda n: f'Form Template {n}')
    version = 1
    description = 'Formulário de teste'


class FormFieldFactory(factory.Factory):
    class Meta:
        model = FormField

    class Params:
        form_template = None

    @factory.lazy_attribute
    def form_template_id(self):
        if self.form_template is None:
            raise ValueError('form_template must be provided')
        return self.form_template.id

    field_key = factory.Sequence(lambda n: f'field_{n}')
    label = factory.Sequence(lambda n: f'Field Label {n}')
    field_type = 'text'
    help_text = None
    is_required = False
    order_index = factory.Sequence(lambda n: n)
    options = None
    validation_rules = None


class ProcessInstanceFactory(factory.Factory):
    class Meta:
        model = ProcessInstance

    class Params:
        template_version = None

    @factory.lazy_attribute
    def template_version_id(self):
        if self.template_version is None:
            raise ValueError('template_version must be provided')
        return self.template_version.id

    code = factory.Sequence(lambda n: f'VAL-2026-{n:04d}')
    title = factory.Sequence(lambda n: f'Processo de Validação {n}')
    status = 'SUBMISSION'
    started_at = None
    closed_at = None
    closure_reason = None

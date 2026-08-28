import factory

from pivma.core.database.models import (
    Institution,
    InstitutionalChange,
    Laboratory,
    UserInstitutionalAffiliation,
)


class InstitutionFactory(factory.Factory):
    class Meta:
        model = Institution

    name = factory.Sequence(lambda number: f'Institution {number}')


class LaboratoryFactory(factory.Factory):
    class Meta:
        model = Laboratory

    class Params:
        institution = None

    @factory.lazy_attribute
    def institution_id(self):
        if self.institution is None:
            raise ValueError('institution must be a persisted Institution')
        return self.institution.id

    name = factory.Sequence(lambda number: f'Laboratory {number}')


class UserInstitutionalAffiliationFactory(factory.Factory):
    class Meta:
        model = UserInstitutionalAffiliation

    class Params:
        user = None
        institution = None
        laboratory = None

    @factory.lazy_attribute
    def user_id(self):
        if self.user is None:
            raise ValueError('user must be a persisted User')
        return self.user.id

    @factory.lazy_attribute
    def institution_id(self):
        if self.institution is None:
            raise ValueError('institution must be a persisted Institution')
        return self.institution.id

    @factory.lazy_attribute
    def laboratory_id(self):
        return None if self.laboratory is None else self.laboratory.id


class InstitutionalChangeFactory(factory.Factory):
    class Meta:
        model = InstitutionalChange

    action = 'institution.created'
    target_type = 'institution'
    target_id = factory.LazyFunction(factory.Faker('uuid4'))

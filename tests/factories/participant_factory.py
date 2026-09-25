import factory

from pivma.core.database.models import Assignment, ConflictInterestDeclaration


class AssignmentFactory(factory.Factory):
    class Meta:
        model = Assignment

    class Params:
        process = None
        user = None
        assigner = None
        laboratory = None

    @factory.lazy_attribute
    def process_instance_id(self):
        if self.process is None:
            raise ValueError('process must be a persisted ProcessInstance')
        return self.process.id

    @factory.lazy_attribute
    def user_id(self):
        if self.user is None:
            raise ValueError('user must be a persisted User')
        return self.user.id

    @factory.lazy_attribute
    def assigned_by(self):
        assigner = self.assigner or self.user
        if assigner is None:
            raise ValueError('assigner or user must be a persisted User')
        return assigner.id

    @factory.lazy_attribute
    def laboratory_id(self):
        return None if self.laboratory is None else self.laboratory.id

    role_key = 'study_manager'
    revoked_at = None


class ConflictInterestDeclarationFactory(factory.Factory):
    class Meta:
        model = ConflictInterestDeclaration

    class Params:
        assignment = None

    @factory.lazy_attribute
    def assignment_id(self):
        if self.assignment is None:
            raise ValueError('assignment must be a persisted Assignment')
        return self.assignment.id

    has_conflict = False
    justification = factory.Sequence(
        lambda n: f'Justificativa de declaração {n}'
    )


async def grant_cargo(session, *, process_id, user, role_key):
    """Dá ao usuário um cargo de processo por atribuição ativa (Spec 030).

    Jeito padrão desta feature de colocar um usuário num cargo nos testes:
    as concessões de atividade são dadas a cargos, e o cargo de processo vem
    de uma `Assignment` ativa.
    """
    assignment = Assignment(
        process_instance_id=process_id,
        user_id=user.id,
        assigned_by=user.id,
        role_key=role_key,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment

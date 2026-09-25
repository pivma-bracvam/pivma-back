from datetime import datetime, timedelta

import factory

from pivma.core.database.models import RoleAssignmentInvite


class InviteFactory(factory.Factory):
    class Meta:
        model = RoleAssignmentInvite

    class Params:
        process = None
        laboratory = None

    @factory.lazy_attribute
    def process_instance_id(self):
        if self.process is None:
            raise ValueError('process must be a persisted ProcessInstance')
        return self.process.id

    @factory.lazy_attribute
    def laboratory_id(self):
        return None if self.laboratory is None else self.laboratory.id

    role_key = 'statistician'
    email = factory.Sequence(lambda n: f'convidado{n}@exemplo.org')
    token_hash = factory.Sequence(lambda n: f'token-hash-{n}')
    channel = 'link'
    status = 'pending'
    expires_at = factory.LazyFunction(
        lambda: datetime.utcnow() + timedelta(hours=1)
    )
    accepted_at = None
    accepted_by = None
    revoked_at = None
    revoked_by = None

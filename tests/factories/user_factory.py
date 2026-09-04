import factory

from pivma.core.database.models import User
from pivma.core.security import hash_password


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'test{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password_hash = factory.LazyFunction(
        lambda: hash_password('Factory-Passphrase-2026')
    )
    full_name = factory.LazyAttribute(lambda obj: f'User {obj.username}')

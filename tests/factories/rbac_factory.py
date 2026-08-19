import factory

from pivma.core.database.models import AccessProfile, UserAccessProfile


class AccessProfileFactory(factory.Factory):
    class Meta:
        model = AccessProfile

    system_key = None
    name = factory.Sequence(lambda n: f'Profile {n}')
    description = 'Test access profile'


class UserAccessProfileFactory(factory.Factory):
    class Meta:
        model = UserAccessProfile

    class Params:
        user = None
        profile = None

    @factory.lazy_attribute
    def user_id(self):
        if self.user is None:
            raise ValueError('user must be a persisted User')
        return self.user.id

    @factory.lazy_attribute
    def profile_id(self):
        if self.profile is None:
            raise ValueError('profile must be a persisted AccessProfile')
        return self.profile.id

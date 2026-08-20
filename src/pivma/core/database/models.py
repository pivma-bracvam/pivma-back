from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, column, func
from sqlalchemy.orm import (
    Mapped,
    declared_attr,
    mapped_column,
    registry,
    relationship,
)

table_registry = registry()


@dataclass(init=False)
class AuditMixin:
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(init=False, server_default=func.now())

    @declared_attr
    def updated_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(init=False, nullable=True, onupdate=func.now())

    @declared_attr
    def deleted_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(init=False, nullable=True)

    @declared_attr
    def created_by(cls) -> Mapped[Optional[UUID]]:
        return mapped_column(
            ForeignKey(
                'users.id',
                name=f'fk_{cls.__tablename__}_created_by',
                use_alter=True,
            ),
            nullable=True,
            default=None,
        )

    @declared_attr
    def updated_by(cls) -> Mapped[Optional[UUID]]:
        return mapped_column(
            ForeignKey(
                'users.id',
                name=f'fk_{cls.__tablename__}_updated_by',
                use_alter=True,
            ),
            nullable=True,
            default=None,
        )

    @declared_attr
    def deleted_by(cls) -> Mapped[Optional[UUID]]:
        return mapped_column(
            ForeignKey(
                'users.id',
                name=f'fk_{cls.__tablename__}_deleted_by',
                use_alter=True,
            ),
            nullable=True,
            default=None,
        )

    def set_creation_audit(self, user_id: UUID):
        self.created_at = func.now()
        self.created_by = user_id

    def set_update_audit(self, user_id: UUID):
        self.updated_at = func.now()
        self.updated_by = user_id

    def set_deletion_audit(self, user_id: UUID):
        self.deleted_at = func.now()
        self.deleted_by = user_id


@table_registry.mapped_as_dataclass
class User(AuditMixin):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )

    username: Mapped[str]
    email: Mapped[str] = mapped_column()
    password_hash: Mapped[str]

    __table_args__ = (
        Index(
            'uq_users_username_ci',
            func.lower(column('username')),
            unique=True,
            postgresql_where=(column('deleted_at').is_(None)),
        ),
        Index(
            'uq_users_email_ci',
            func.lower(column('email')),
            unique=True,
            postgresql_where=(column('deleted_at').is_(None)),
        ),
    )


@table_registry.mapped_as_dataclass
class AccessProfile(AuditMixin):
    __tablename__ = 'access_profiles'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    system_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500))
    permissions: Mapped[list['AccessProfilePermission']] = relationship(
        back_populates='profile', init=False
    )
    assignments: Mapped[list['UserAccessProfile']] = relationship(
        back_populates='profile', init=False
    )

    __table_args__ = (
        Index(
            'uq_access_profiles_name_ci_active',
            func.lower(column('name')),
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class Permission(AuditMixin):
    __tablename__ = 'permissions'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(500))
    profiles: Mapped[list['AccessProfilePermission']] = relationship(
        back_populates='permission', init=False
    )


@table_registry.mapped_as_dataclass
class AccessProfilePermission(AuditMixin):
    __tablename__ = 'access_profile_permissions'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('access_profiles.id'))
    permission_id: Mapped[UUID] = mapped_column(ForeignKey('permissions.id'))
    profile: Mapped[AccessProfile] = relationship(
        back_populates='permissions', init=False
    )
    permission: Mapped[Permission] = relationship(
        back_populates='profiles', init=False
    )

    __table_args__ = (
        Index(
            'uq_access_profile_permissions_active',
            'profile_id',
            'permission_id',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class UserAccessProfile(AuditMixin):
    __tablename__ = 'user_access_profiles'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('access_profiles.id'))
    profile: Mapped[AccessProfile] = relationship(
        back_populates='assignments', init=False
    )

    __table_args__ = (
        Index(
            'uq_user_access_profiles_active',
            'user_id',
            'profile_id',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class RbacChange(AuditMixin):
    __tablename__ = 'rbac_changes'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID]

    __table_args__ = (
        Index(
            'ix_rbac_changes_created_at_id_desc',
            column('created_at').desc(),
            column('id').desc(),
        ),
    )

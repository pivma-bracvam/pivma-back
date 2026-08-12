from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, column, func
from sqlalchemy.orm import (
    Mapped,
    declared_attr,
    mapped_column,
    registry,
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

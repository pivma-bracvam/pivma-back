from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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


# ==========================================
# RBAC & USER MODELS
# ==========================================


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
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500))
    system_key: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, default=None
    )
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


# ==========================================
# INSTITUTIONAL AFFILIATION MODELS
# ==========================================


@table_registry.mapped_as_dataclass
class Institution(AuditMixin):
    __tablename__ = 'institutions'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255))

    __table_args__ = (
        Index(
            'uq_institutions_name_ci_active',
            func.lower(column('name')),
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
        Index('ix_institutions_name_id', func.lower(column('name')), 'id'),
    )


@table_registry.mapped_as_dataclass
class Laboratory(AuditMixin):
    __tablename__ = 'laboratories'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    institution_id: Mapped[UUID] = mapped_column(ForeignKey('institutions.id'))
    name: Mapped[str] = mapped_column(String(255))

    __table_args__ = (
        UniqueConstraint(
            'id', 'institution_id', name='uq_laboratories_id_institution_id'
        ),
        Index(
            'uq_laboratories_institution_name_ci_active',
            'institution_id',
            func.lower(column('name')),
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
        Index(
            'ix_laboratories_institution_name_id',
            'institution_id',
            func.lower(column('name')),
            'id',
        ),
    )


@table_registry.mapped_as_dataclass
class UserInstitutionalAffiliation(AuditMixin):
    __tablename__ = 'user_institutional_affiliations'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    institution_id: Mapped[UUID] = mapped_column(ForeignKey('institutions.id'))
    laboratory_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True, default=None
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['laboratory_id', 'institution_id'],
            ['laboratories.id', 'laboratories.institution_id'],
            name='fk_affiliations_laboratory_institution',
        ),
        Index(
            'uq_affiliations_active_institution',
            'user_id',
            'institution_id',
            unique=True,
            postgresql_where=(
                column('deleted_at').is_(None)
                & column('laboratory_id').is_(None)
            ),
        ),
        Index(
            'uq_affiliations_active_laboratory',
            'user_id',
            'institution_id',
            'laboratory_id',
            unique=True,
            postgresql_where=(
                column('deleted_at').is_(None)
                & column('laboratory_id').is_not(None)
            ),
        ),
        Index(
            'ix_affiliations_active_scope',
            'user_id',
            'institution_id',
            'laboratory_id',
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class InstitutionalChange(AuditMixin):
    __tablename__ = 'institutional_changes'

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
            'ix_institutional_changes_created_at_id_desc',
            column('created_at').desc(),
            column('id').desc(),
        ),
    )


# ==========================================
# PROCESS ENGINE & FORM MODELS
# ==========================================


@table_registry.mapped_as_dataclass
class ProcessTemplate(AuditMixin):
    __tablename__ = 'process_templates'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    versions: Mapped[list['ProcessTemplateVersion']] = relationship(
        back_populates='template', init=False
    )


@table_registry.mapped_as_dataclass
class ProcessTemplateVersion(AuditMixin):
    __tablename__ = 'process_template_versions'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_templates.id')
    )
    version_number: Mapped[int] = mapped_column(Integer)
    definition_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    template: Mapped[ProcessTemplate] = relationship(
        back_populates='versions', init=False
    )
    instances: Mapped[list['ProcessInstance']] = relationship(
        back_populates='template_version', init=False
    )

    __table_args__ = (
        Index(
            'uq_process_template_version_active',
            'template_id',
            'version_number',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class FormTemplate(AuditMixin):
    __tablename__ = 'form_templates'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    fields: Mapped[list['FormField']] = relationship(
        back_populates='form_template', init=False
    )
    instances: Mapped[list['FormInstance']] = relationship(
        back_populates='form_template', init=False
    )


@table_registry.mapped_as_dataclass
class FormField(AuditMixin):
    __tablename__ = 'form_fields'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    form_template_id: Mapped[UUID] = mapped_column(
        ForeignKey('form_templates.id')
    )
    field_key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    field_type: Mapped[str] = mapped_column(String(32))
    help_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, default=None
    )
    validation_rules: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=None
    )

    form_template: Mapped[FormTemplate] = relationship(
        back_populates='fields', init=False
    )

    __table_args__ = (
        Index(
            'uq_form_fields_key_active',
            'form_template_id',
            'field_key',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class ProcessInstance(AuditMixin):
    __tablename__ = 'process_instances'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    template_version_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_template_versions.id')
    )
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default='SUBMISSION')
    started_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )
    closure_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    template_version: Mapped[ProcessTemplateVersion] = relationship(
        back_populates='instances', init=False
    )
    phases: Mapped[list['Phase']] = relationship(
        back_populates='process_instance', init=False
    )
    activities: Mapped[list['ActivityInstance']] = relationship(
        back_populates='process_instance', init=False
    )
    assignments: Mapped[list['Assignment']] = relationship(
        back_populates='process_instance', init=False
    )
    artifacts: Mapped[list['Artifact']] = relationship(
        back_populates='process_instance', init=False
    )
    decisions: Mapped[list['Decision']] = relationship(
        back_populates='process_instance', init=False
    )
    audit_events: Mapped[list['AuditEvent']] = relationship(
        back_populates='process_instance', init=False
    )


@table_registry.mapped_as_dataclass
class Phase(AuditMixin):
    __tablename__ = 'phases'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    order_index: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default='NOT_STARTED')

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='phases', init=False
    )
    activities: Mapped[list['ActivityInstance']] = relationship(
        back_populates='phase', init=False
    )


@table_registry.mapped_as_dataclass
class ActivityInstance(AuditMixin):
    __tablename__ = 'activity_instances'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    phase_id: Mapped[UUID] = mapped_column(ForeignKey('phases.id'))
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    order_index: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default='BLOCKED')
    blocked_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='activities', init=False
    )
    phase: Mapped[Phase] = relationship(
        back_populates='activities', init=False
    )
    runs: Mapped[list['ActivityRun']] = relationship(
        back_populates='activity_instance', init=False
    )
    dependencies: Mapped[list['ActivityDependency']] = relationship(
        foreign_keys='[ActivityDependency.dependent_activity_id]',
        back_populates='dependent_activity',
        init=False,
    )


@table_registry.mapped_as_dataclass
class ActivityDependency(AuditMixin):
    __tablename__ = 'activity_dependencies'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    dependent_activity_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_instances.id')
    )
    required_activity_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('activity_instances.id'), nullable=True, default=None
    )
    required_status: Mapped[str] = mapped_column(
        String(32), default='COMPLETED'
    )
    condition_type: Mapped[str] = mapped_column(
        String(32), default='ACTIVITY_COMPLETED'
    )

    dependent_activity: Mapped[ActivityInstance] = relationship(
        foreign_keys=[dependent_activity_id],
        back_populates='dependencies',
        init=False,
    )
    required_activity: Mapped[Optional[ActivityInstance]] = relationship(
        foreign_keys=[required_activity_id], init=False
    )


@table_registry.mapped_as_dataclass
class ActivityRun(AuditMixin):
    __tablename__ = 'activity_runs'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    activity_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_instances.id')
    )
    run_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default='IN_PROGRESS')
    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )
    execution_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    activity_instance: Mapped[ActivityInstance] = relationship(
        back_populates='runs', init=False
    )
    tasks: Mapped[list['Task']] = relationship(
        back_populates='activity_run', init=False
    )
    form_instances: Mapped[list['FormInstance']] = relationship(
        back_populates='activity_run', init=False
    )
    artifacts: Mapped[list['Artifact']] = relationship(
        back_populates='activity_run', init=False
    )
    decisions: Mapped[list['Decision']] = relationship(
        back_populates='activity_run', init=False
    )

    __table_args__ = (
        Index(
            'uq_activity_runs_number_active',
            'activity_instance_id',
            'run_number',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class Task(AuditMixin):
    __tablename__ = 'tasks'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    activity_run_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_runs.id')
    )
    title: Mapped[str] = mapped_column(String(255))
    assigned_role: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    assigned_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('users.id'), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(32), default='READY')
    due_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )

    activity_run: Mapped[ActivityRun] = relationship(
        back_populates='tasks', init=False
    )


@table_registry.mapped_as_dataclass
class FormInstance(AuditMixin):
    __tablename__ = 'form_instances'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    form_template_id: Mapped[UUID] = mapped_column(
        ForeignKey('form_templates.id')
    )
    activity_run_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_runs.id')
    )
    is_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )

    form_template: Mapped[FormTemplate] = relationship(
        back_populates='instances', init=False
    )
    activity_run: Mapped[ActivityRun] = relationship(
        back_populates='form_instances', init=False
    )
    values: Mapped[list['FormValue']] = relationship(
        back_populates='form_instance', init=False
    )
    reviews: Mapped[list['FieldReview']] = relationship(
        back_populates='form_instance', init=False
    )


@table_registry.mapped_as_dataclass
class FormValue(AuditMixin):
    __tablename__ = 'form_values'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    form_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('form_instances.id')
    )
    form_field_id: Mapped[UUID] = mapped_column(ForeignKey('form_fields.id'))
    text_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    numeric_value: Mapped[Optional[float]] = mapped_column(
        Numeric, nullable=True, default=None
    )
    boolean_value: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=None
    )
    date_value: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, default=None
    )
    json_value: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, default=None
    )
    file_attachment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('artifacts.id'), nullable=True, default=None
    )

    form_instance: Mapped[FormInstance] = relationship(
        back_populates='values', init=False
    )
    form_field: Mapped[FormField] = relationship(init=False)

    __table_args__ = (
        Index(
            'uq_form_values_active',
            'form_instance_id',
            'form_field_id',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class FieldReview(AuditMixin):
    __tablename__ = 'field_reviews'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    form_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('form_instances.id')
    )
    form_field_id: Mapped[UUID] = mapped_column(ForeignKey('form_fields.id'))
    activity_run_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_runs.id')
    )
    status: Mapped[str] = mapped_column(String(32))
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    comments: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )

    form_instance: Mapped[FormInstance] = relationship(
        back_populates='reviews', init=False
    )
    form_field: Mapped[FormField] = relationship(init=False)

    __table_args__ = (
        Index(
            'uq_field_reviews_active',
            'form_instance_id',
            'form_field_id',
            'activity_run_id',
            unique=True,
            postgresql_where=column('deleted_at').is_(None),
        ),
    )


@table_registry.mapped_as_dataclass
class Artifact(AuditMixin):
    __tablename__ = 'artifacts'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    activity_run_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_runs.id')
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default=None
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None
    )
    checksum_sha256: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None
    )
    metadata_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(32), default='SUBMITTED')

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='artifacts', init=False
    )
    activity_run: Mapped[ActivityRun] = relationship(
        back_populates='artifacts', init=False
    )


@table_registry.mapped_as_dataclass
class Decision(AuditMixin):
    __tablename__ = 'decisions'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    activity_run_id: Mapped[UUID] = mapped_column(
        ForeignKey('activity_runs.id')
    )
    decision_type: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    justification: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    decided_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='decisions', init=False
    )
    activity_run: Mapped[ActivityRun] = relationship(
        back_populates='decisions', init=False
    )


@table_registry.mapped_as_dataclass
class Assignment(AuditMixin):
    __tablename__ = 'assignments'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    role_key: Mapped[str] = mapped_column(String(64))
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    assigned_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None
    )
    laboratory_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('laboratories.id'), nullable=True, default=None
    )

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='assignments', init=False
    )

    __table_args__ = (
        Index(
            'uq_assignments_active',
            'process_instance_id',
            'user_id',
            'role_key',
            unique=True,
            postgresql_where=(
                column('revoked_at').is_(None) & column('deleted_at').is_(None)
            ),
        ),
    )


@table_registry.mapped_as_dataclass
class ConflictInterestDeclaration(AuditMixin):
    __tablename__ = 'conflict_interest_declarations'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    assignment_id: Mapped[UUID] = mapped_column(ForeignKey('assignments.id'))
    has_conflict: Mapped[bool] = mapped_column(Boolean)
    justification: Mapped[str] = mapped_column(Text)
    declared_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )

    __table_args__ = (
        Index(
            'ix_conflict_declarations_assignment_time',
            'assignment_id',
            column('declared_at').desc(),
            column('id').desc(),
        ),
    )


@table_registry.mapped_as_dataclass
class AuditEvent(AuditMixin):
    __tablename__ = 'audit_events'

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        insert_default=uuid4,
        default_factory=uuid4,
    )
    process_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey('process_instances.id')
    )
    event_type: Mapped[str] = mapped_column(String(64))
    activity_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('activity_runs.id'), nullable=True, default=None
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey('users.id'), nullable=True, default=None
    )
    context_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=None
    )
    occurred_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default_factory=datetime.utcnow
    )

    process_instance: Mapped[ProcessInstance] = relationship(
        back_populates='audit_events', init=False
    )

    __table_args__ = (
        Index(
            'ix_audit_events_process_time',
            'process_instance_id',
            column('occurred_at').desc(),
        ),
    )

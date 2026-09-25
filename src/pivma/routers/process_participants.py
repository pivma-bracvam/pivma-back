from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from pivma.core.authorization import (
    can_manage_participants,
    can_manage_role_assignment,
    compute_effectiveness_map,
    declarations_by_assignment,
    latest_declarations_map,
    participant_read_scope,
)
from pivma.core.database.models import (
    Assignment,
    AuditEvent,
    ConflictInterestDeclaration,
    ProcessInstance,
    RoleAssignmentInvite,
)
from pivma.core.invite_service import (
    create_invite,
    invite_public_kwargs,
    resend_invite,
    revoke_invite,
)
from pivma.core.participant_service import create_assignment
from pivma.core.process_engine import (
    IMMUTABLE_PROCESS_STATUSES,
    ConflictError,
    NotFoundError,
    _maybe_close_role_assignment_activity,  # noqa: PLC2701
    utc_now,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.schemas import (
    ConflictDeclarationCreate,
    ConflictDeclarationPublic,
    InviteCreate,
    InviteCreatedResponse,
    InvitePublic,
    ParticipantAssignmentCreate,
    ParticipantAssignmentPublic,
    ParticipantHistoryItem,
    ParticipantHistoryPage,
)

router = APIRouter(prefix='/processes', tags=['Process Participants'])

MAX_HISTORY_LIMIT = 200


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.CONFLICT, detail=detail)


def forbidden() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.FORBIDDEN, detail='Forbidden')


def _assignment_event_context(
    assignment: Assignment, *, result: str, source: str
) -> dict:
    return {
        'assignment_id': str(assignment.id),
        'participant_user_id': str(assignment.user_id),
        'role_key': assignment.role_key,
        'laboratory_id': (
            str(assignment.laboratory_id)
            if assignment.laboratory_id is not None
            else None
        ),
        'result': result,
        'source': source,
    }


async def _build_participant_publics(
    session: Session, process_id: UUID, assignments: list[Assignment]
) -> list[ParticipantAssignmentPublic]:
    effectiveness = await compute_effectiveness_map(session, assignments)
    declarations = await latest_declarations_map(
        session, [assignment.id for assignment in assignments]
    )
    publics = []
    for assignment in assignments:
        declaration = declarations.get(assignment.id)
        publics.append(
            ParticipantAssignmentPublic(
                id=assignment.id,
                process_id=process_id,
                user_id=assignment.user_id,
                role_key=assignment.role_key,
                laboratory_id=assignment.laboratory_id,
                assigned_by=assignment.assigned_by,
                assigned_at=assignment.assigned_at,
                revoked_at=assignment.revoked_at,
                active=(
                    assignment.revoked_at is None
                    and assignment.deleted_at is None
                ),
                effective=effectiveness.get(assignment.id, False),
                has_conflict=(
                    declaration.has_conflict if declaration else None
                ),
                latest_declared_at=(
                    declaration.declared_at if declaration else None
                ),
            )
        )
    return publics


async def _get_active_process(session: Session, process_id: UUID):
    return await session.get(ProcessInstance, process_id)


@router.get(
    '/{process_id}/participants',
    response_model=list[ParticipantAssignmentPublic],
    status_code=HTTPStatus.OK,
)
async def list_participants(
    process_id: UUID, session: Session, current_user: CurrentUser
):
    scope = await participant_read_scope(session, current_user.id, process_id)
    if scope is None:
        raise forbidden()

    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')

    stmt = select(Assignment).where(
        Assignment.process_instance_id == process_id,
        Assignment.revoked_at.is_(None),
        Assignment.deleted_at.is_(None),
    )
    if scope == 'self':
        stmt = stmt.where(Assignment.user_id == current_user.id)
    stmt = stmt.order_by(Assignment.assigned_at.desc(), Assignment.id.desc())

    assignments = list(await session.scalars(stmt))
    return await _build_participant_publics(session, process_id, assignments)


@router.post(
    '/{process_id}/participants',
    response_model=ParticipantAssignmentPublic,
    status_code=HTTPStatus.CREATED,
)
async def create_participant(
    process_id: UUID,
    payload: ParticipantAssignmentCreate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    if not await can_manage_role_assignment(
        session, current_user.id, process_id, payload.role_key
    ):
        raise forbidden()

    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')
    if process.deleted_at is not None:
        raise conflict('Processo inativo.')
    if process.status in IMMUTABLE_PROCESS_STATUSES:
        raise conflict('Processo encerrado não aceita novos participantes.')

    try:
        assignment = await create_assignment(
            session,
            process,
            user_id=payload.user_id,
            role_key=payload.role_key,
            laboratory_id=payload.laboratory_id,
            actor_id=current_user.id,
            source='api',
        )
    except NotFoundError as e:
        raise not_found(str(e)) from e
    except ConflictError as e:
        raise conflict(str(e)) from e

    await session.commit()
    await session.refresh(assignment)

    publics = await _build_participant_publics(
        session, process_id, [assignment]
    )
    return publics[0]


@router.delete(
    '/{process_id}/participants/{assignment_id}',
    status_code=HTTPStatus.NO_CONTENT,
)
async def revoke_participant(
    process_id: UUID,
    assignment_id: UUID,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
) -> Response:
    # A autorização depende do papel da designação (FR-001/FR-003), que só
    # é conhecido depois de buscá-la; para quem não tem a autorização
    # genérica (Spec 006), a busca acontece de qualquer forma (mesmo custo
    # de uma consulta indexada por PK) sem expor a existência da designação
    # antes de decidir 403 — quando não encontrada, cai de volta na regra
    # genérica, preservando o comportamento anterior a esta feature.
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.process_instance_id == process_id,
        )
    )
    if assignment is not None:
        authorized = await can_manage_role_assignment(
            session, current_user.id, process_id, assignment.role_key
        )
    else:
        authorized = await can_manage_participants(
            session, current_user.id, process_id
        )
    if not authorized:
        raise forbidden()
    if assignment is None:
        raise not_found('Designação não encontrada.')
    process = await session.get(ProcessInstance, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')
    if process.status in IMMUTABLE_PROCESS_STATUSES:
        raise conflict('Processo encerrado não aceita alterações.')
    if assignment.revoked_at is not None:
        raise conflict('Designação já revogada.')

    assignment.revoked_at = utc_now()
    assignment.set_update_audit(current_user.id)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            user_id=current_user.id,
            event_type='PARTICIPANT_REVOKED',
            context_data=_assignment_event_context(
                assignment, result='success', source='api'
            ),
        )
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.post(
    '/{process_id}/participants/{assignment_id}/conflicts',
    response_model=ConflictDeclarationPublic,
    status_code=HTTPStatus.CREATED,
)
async def declare_conflict(
    process_id: UUID,
    assignment_id: UUID,
    payload: ConflictDeclarationCreate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.process_instance_id == process_id,
        )
    )
    if assignment is None or assignment.user_id != current_user.id:
        raise forbidden()
    process = await session.get(ProcessInstance, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')
    if process.status in IMMUTABLE_PROCESS_STATUSES:
        raise conflict('Processo encerrado não aceita conflitos.')
    if assignment.revoked_at is not None:
        raise conflict('Designação revogada.')

    declaration = ConflictInterestDeclaration(
        assignment_id=assignment.id,
        has_conflict=payload.has_conflict,
        justification=payload.justification,
    )
    declaration.set_creation_audit(current_user.id)
    session.add(declaration)
    await session.flush()

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            user_id=current_user.id,
            event_type='CONFLICT_DECLARED',
            context_data={
                **_assignment_event_context(
                    assignment, result='success', source='api'
                ),
                'has_conflict': payload.has_conflict,
                'justification': payload.justification,
            },
        )
    )
    await session.commit()
    await session.refresh(declaration)

    return ConflictDeclarationPublic(
        id=declaration.id,
        assignment_id=declaration.assignment_id,
        has_conflict=declaration.has_conflict,
        justification=declaration.justification,
        declared_at=declaration.declared_at,
    )


@router.get(
    '/{process_id}/participants/history',
    response_model=ParticipantHistoryPage,
    status_code=HTTPStatus.OK,
)
async def get_participant_history(
    process_id: UUID,
    session: Session,
    current_user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_HISTORY_LIMIT),
):
    scope = await participant_read_scope(session, current_user.id, process_id)
    if scope is None:
        raise forbidden()

    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')

    stmt = select(Assignment).where(
        Assignment.process_instance_id == process_id,
        Assignment.deleted_at.is_(None),
    )
    if scope == 'self':
        stmt = stmt.where(Assignment.user_id == current_user.id)
    stmt = (
        stmt
        .order_by(Assignment.assigned_at.desc(), Assignment.id.desc())
        .offset(offset)
        .limit(limit)
    )

    assignments = list(await session.scalars(stmt))
    publics = await _build_participant_publics(
        session, process_id, assignments
    )
    declarations_map = await declarations_by_assignment(
        session, [assignment.id for assignment in assignments]
    )

    items = [
        ParticipantHistoryItem(
            assignment=public,
            declarations=[
                ConflictDeclarationPublic(
                    id=declaration.id,
                    assignment_id=declaration.assignment_id,
                    has_conflict=declaration.has_conflict,
                    justification=declaration.justification,
                    declared_at=declaration.declared_at,
                )
                for declaration in declarations_map.get(public.id, [])
            ],
        )
        for public in publics
    ]

    return ParticipantHistoryPage(offset=offset, limit=limit, items=items)


# ==========================================
# ROLE ASSIGNMENT INVITES (Spec 028)
# ==========================================


def _invite_public(
    invite: RoleAssignmentInvite, *, token: str | None = None
) -> InvitePublic:
    kwargs = invite_public_kwargs(invite)
    if token is not None:
        return InviteCreatedResponse(**kwargs, token=token)
    return InvitePublic(**kwargs)


async def _get_invite_or_404(
    session: Session, process_id: UUID, invite_id: UUID
) -> RoleAssignmentInvite:
    invite = await session.scalar(
        select(RoleAssignmentInvite).where(
            RoleAssignmentInvite.id == invite_id,
            RoleAssignmentInvite.process_instance_id == process_id,
            RoleAssignmentInvite.deleted_at.is_(None),
        )
    )
    if invite is None:
        raise not_found('Convite não encontrado.')
    return invite


@router.post(
    '/{process_id}/participants/invites',
    response_model=InviteCreatedResponse,
    status_code=HTTPStatus.CREATED,
)
async def create_participant_invite(
    process_id: UUID,
    payload: InviteCreate,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    if not await can_manage_role_assignment(
        session, current_user.id, process_id, payload.role_key
    ):
        raise forbidden()

    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')
    if process.deleted_at is not None:
        raise conflict('Processo inativo.')
    if process.status in IMMUTABLE_PROCESS_STATUSES:
        raise conflict('Processo encerrado não aceita novos convites.')

    try:
        invite, token = await create_invite(
            session,
            process,
            email=payload.email,
            role_key=payload.role_key,
            laboratory_id=payload.laboratory_id,
            channel=payload.channel,
            actor_id=current_user.id,
            expiration_hours=settings.INVITE_EXPIRATION_HOURS,
        )
    except NotFoundError as e:
        raise not_found(str(e)) from e
    except ConflictError as e:
        raise conflict(str(e)) from e

    await session.commit()
    await session.refresh(invite)
    return _invite_public(invite, token=token)


@router.get(
    '/{process_id}/participants/invites',
    response_model=list[InvitePublic],
    status_code=HTTPStatus.OK,
)
async def list_participant_invites(
    process_id: UUID, session: Session, current_user: CurrentUser
):
    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')

    stmt = (
        select(RoleAssignmentInvite)
        .where(
            RoleAssignmentInvite.process_instance_id == process_id,
            RoleAssignmentInvite.deleted_at.is_(None),
        )
        .order_by(RoleAssignmentInvite.created_at.desc())
    )
    invites = list(await session.scalars(stmt))

    visible = []
    for invite in invites:
        if await can_manage_role_assignment(
            session, current_user.id, process_id, invite.role_key
        ):
            visible.append(_invite_public(invite))
    return visible


@router.post(
    '/{process_id}/participants/invites/{invite_id}/resend',
    response_model=InviteCreatedResponse,
    status_code=HTTPStatus.OK,
)
async def resend_participant_invite(
    process_id: UUID,
    invite_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    invite = await _get_invite_or_404(session, process_id, invite_id)
    if not await can_manage_role_assignment(
        session, current_user.id, process_id, invite.role_key
    ):
        raise forbidden()

    try:
        invite, token = await resend_invite(
            session,
            invite,
            actor_id=current_user.id,
            expiration_hours=settings.INVITE_EXPIRATION_HOURS,
        )
    except ConflictError as e:
        raise conflict(str(e)) from e

    await session.commit()
    await session.refresh(invite)
    return _invite_public(invite, token=token)


@router.post(
    '/{process_id}/participants/invites/{invite_id}/revoke',
    response_model=InvitePublic,
    status_code=HTTPStatus.OK,
)
async def revoke_participant_invite(
    process_id: UUID,
    invite_id: UUID,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    invite = await _get_invite_or_404(session, process_id, invite_id)
    if not await can_manage_role_assignment(
        session, current_user.id, process_id, invite.role_key
    ):
        raise forbidden()

    try:
        invite = await revoke_invite(session, invite, actor_id=current_user.id)
    except ConflictError as e:
        raise conflict(str(e)) from e

    process = await session.get(ProcessInstance, process_id)
    if process is not None:
        await _maybe_close_role_assignment_activity(
            session, process, invite.role_key, current_user.id
        )

    await session.commit()
    await session.refresh(invite)
    return _invite_public(invite)

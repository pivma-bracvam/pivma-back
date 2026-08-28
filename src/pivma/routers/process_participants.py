from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pivma.core.authorization import (
    LABORATORY_ROLE_KEYS,
    can_manage_participants,
    compute_effectiveness_map,
    declarations_by_assignment,
    has_active_laboratory_affiliation,
    latest_declarations_map,
    participant_read_scope,
)
from pivma.core.database.models import (
    Assignment,
    AuditEvent,
    ConflictInterestDeclaration,
    Laboratory,
    ProcessInstance,
    User,
)
from pivma.core.process_engine import utc_now
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.schemas import (
    ConflictDeclarationCreate,
    ConflictDeclarationPublic,
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
    if not await can_manage_participants(session, current_user.id, process_id):
        raise forbidden()

    process = await _get_active_process(session, process_id)
    if process is None:
        raise not_found('Processo não encontrado.')
    if process.deleted_at is not None:
        raise conflict('Processo inativo.')

    target_user = await session.get(User, payload.user_id)
    if target_user is None:
        raise not_found('Usuário não encontrado.')
    if target_user.deleted_at is not None:
        raise conflict('Usuário inativo.')

    laboratory = None
    if payload.role_key in LABORATORY_ROLE_KEYS:
        laboratory = await session.get(Laboratory, payload.laboratory_id)
        if laboratory is None:
            raise not_found('Laboratório não encontrado.')
        if laboratory.deleted_at is not None:
            raise conflict('Laboratório inativo.')
        if not await has_active_laboratory_affiliation(
            session, payload.user_id, payload.laboratory_id
        ):
            raise conflict(
                'Usuário sem vínculo laboratorial vigente com o laboratório.'
            )

    assignment = Assignment(
        process_instance_id=process_id,
        user_id=payload.user_id,
        role_key=payload.role_key,
        assigned_by=current_user.id,
        laboratory_id=payload.laboratory_id,
    )
    assignment.set_creation_audit(current_user.id)
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise conflict(
            'Já existe uma designação ativa para este processo, '
            'usuário e papel.'
        ) from None

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            user_id=current_user.id,
            event_type='PARTICIPANT_ASSIGNED',
            context_data=_assignment_event_context(
                assignment, result='success', source='api'
            ),
        )
    )
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
    if not await can_manage_participants(session, current_user.id, process_id):
        raise forbidden()

    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.process_instance_id == process_id,
        )
    )
    if assignment is None:
        raise not_found('Designação não encontrada.')
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

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
    INSTITUTIONAL_READ,
    active_institutional_affiliations,
)
from pivma.core.database.models import (
    Institution,
    InstitutionalChange,
    Laboratory,
    User,
    UserInstitutionalAffiliation,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    TrustedOrigin,
    require_permission,
)
from pivma.schemas import (
    AffiliationCreate,
    AffiliationPublic,
    InstitutionalChangePage,
    InstitutionalChangePublic,
    InstitutionCreate,
    InstitutionPublic,
    InstitutionSummary,
    InstitutionUpdate,
    LaboratoryCreate,
    LaboratoryPublic,
    LaboratorySummary,
    LaboratoryUpdate,
    SelfAffiliationPublic,
)

router = APIRouter(prefix='/institutional', tags=['institutional'])
MAX_HISTORY_LIMIT = 100
ReadUser = Annotated[User, Depends(require_permission(INSTITUTIONAL_READ))]
CatalogManager = Annotated[
    User, Depends(require_permission(INSTITUTIONAL_CATALOGS_MANAGE))
]
AffiliationManager = Annotated[
    User, Depends(require_permission(INSTITUTIONAL_AFFILIATIONS_MANAGE))
]


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.CONFLICT, detail=detail)


async def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise conflict(detail) from None


async def flush_or_conflict(session: Session, detail: str) -> None:
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise conflict(detail) from None


def institution_summary(item: Institution) -> InstitutionSummary:
    return InstitutionSummary(
        id=item.id, name=item.name, active=item.deleted_at is None
    )


def institution_public(item: Institution) -> InstitutionPublic:
    return InstitutionPublic(
        **institution_summary(item).model_dump(),
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


def laboratory_summary(item: Laboratory) -> LaboratorySummary:
    return LaboratorySummary(
        id=item.id, name=item.name, active=item.deleted_at is None
    )


def laboratory_public(item: Laboratory) -> LaboratoryPublic:
    return LaboratoryPublic(
        **laboratory_summary(item).model_dump(),
        institution_id=item.institution_id,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


def record_change(
    session: Session,
    action: str,
    target_type: str,
    target_id: UUID,
    actor_id: UUID,
) -> None:
    change = InstitutionalChange(
        action=action, target_type=target_type, target_id=target_id
    )
    change.set_creation_audit(actor_id)
    session.add(change)


async def get_institution(
    session: Session, institution_id: UUID
) -> Institution:
    item = await session.get(Institution, institution_id)
    if item is None:
        raise not_found('Institution not found')
    return item


async def get_laboratory(session: Session, laboratory_id: UUID) -> Laboratory:
    item = await session.get(Laboratory, laboratory_id)
    if item is None:
        raise not_found('Laboratory not found')
    return item


async def affiliation_public(
    session: Session, item: UserInstitutionalAffiliation
) -> AffiliationPublic:
    user = await session.get(User, item.user_id)
    institution = await get_institution(session, item.institution_id)
    laboratory = (
        await get_laboratory(session, item.laboratory_id)
        if item.laboratory_id is not None
        else None
    )
    active = (
        item.deleted_at is None
        and user is not None
        and user.deleted_at is None
        and institution.deleted_at is None
        and (laboratory is None or laboratory.deleted_at is None)
    )
    return AffiliationPublic(
        id=item.id,
        user_id=item.user_id,
        institution=institution_summary(institution),
        laboratory=laboratory_summary(laboratory) if laboratory else None,
        active=active,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


@router.get('/institutions', response_model=list[InstitutionPublic])
async def list_institutions(session: Session, _: ReadUser):
    items = list(
        await session.scalars(
            select(Institution).order_by(
                func.lower(Institution.name), Institution.id
            )
        )
    )
    return [institution_public(item) for item in items]


@router.post(
    '/institutions',
    response_model=InstitutionPublic,
    status_code=HTTPStatus.CREATED,
)
async def create_institution(
    payload: InstitutionCreate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    item = Institution(name=payload.name)
    item.set_creation_audit(actor.id)
    session.add(item)
    await flush_or_conflict(session, 'Institution name already exists')
    record_change(
        session, 'institution.created', 'institution', item.id, actor.id
    )
    await commit_or_conflict(session, 'Institution name already exists')
    await session.refresh(item)
    return institution_public(item)


@router.get('/institutions/{institution_id}', response_model=InstitutionPublic)
async def read_institution(
    institution_id: UUID, session: Session, _: ReadUser
):
    return institution_public(await get_institution(session, institution_id))


@router.patch(
    '/institutions/{institution_id}', response_model=InstitutionPublic
)
async def update_institution(
    institution_id: UUID,
    payload: InstitutionUpdate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    item = await get_institution(session, institution_id)
    if item.deleted_at is not None:
        raise conflict('Institution is inactive')
    item.name = payload.name
    item.set_update_audit(actor.id)
    await flush_or_conflict(session, 'Institution name already exists')
    record_change(
        session, 'institution.updated', 'institution', item.id, actor.id
    )
    await commit_or_conflict(session, 'Institution name already exists')
    await session.refresh(item)
    return institution_public(item)


@router.delete(
    '/institutions/{institution_id}', status_code=HTTPStatus.NO_CONTENT
)
async def deactivate_institution(
    institution_id: UUID,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
) -> Response:
    item = await get_institution(session, institution_id)
    if item.deleted_at is not None:
        raise conflict('Institution is inactive')
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'institution.deactivated', 'institution', item.id, actor.id
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/laboratories', response_model=list[LaboratoryPublic])
async def list_laboratories(session: Session, _: ReadUser):
    items = list(
        await session.scalars(
            select(Laboratory).order_by(
                Laboratory.institution_id,
                func.lower(Laboratory.name),
                Laboratory.id,
            )
        )
    )
    return [laboratory_public(item) for item in items]


@router.post(
    '/laboratories',
    response_model=LaboratoryPublic,
    status_code=HTTPStatus.CREATED,
)
async def create_laboratory(
    payload: LaboratoryCreate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    institution = await get_institution(session, payload.institution_id)
    if institution.deleted_at is not None:
        raise conflict('Institution is inactive')
    item = Laboratory(institution_id=institution.id, name=payload.name)
    item.set_creation_audit(actor.id)
    session.add(item)
    await flush_or_conflict(session, 'Laboratory name already exists')
    record_change(
        session, 'laboratory.created', 'laboratory', item.id, actor.id
    )
    await commit_or_conflict(session, 'Laboratory name already exists')
    await session.refresh(item)
    return laboratory_public(item)


@router.get('/laboratories/{laboratory_id}', response_model=LaboratoryPublic)
async def read_laboratory(laboratory_id: UUID, session: Session, _: ReadUser):
    return laboratory_public(await get_laboratory(session, laboratory_id))


@router.patch('/laboratories/{laboratory_id}', response_model=LaboratoryPublic)
async def update_laboratory(
    laboratory_id: UUID,
    payload: LaboratoryUpdate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    item = await get_laboratory(session, laboratory_id)
    if item.deleted_at is not None:
        raise conflict('Laboratory is inactive')
    item.name = payload.name
    item.set_update_audit(actor.id)
    await flush_or_conflict(session, 'Laboratory name already exists')
    record_change(
        session, 'laboratory.updated', 'laboratory', item.id, actor.id
    )
    await commit_or_conflict(session, 'Laboratory name already exists')
    await session.refresh(item)
    return laboratory_public(item)


@router.delete(
    '/laboratories/{laboratory_id}', status_code=HTTPStatus.NO_CONTENT
)
async def deactivate_laboratory(
    laboratory_id: UUID,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
) -> Response:
    item = await get_laboratory(session, laboratory_id)
    if item.deleted_at is not None:
        raise conflict('Laboratory is inactive')
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'laboratory.deactivated', 'laboratory', item.id, actor.id
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get(
    '/users/{user_id}/affiliations', response_model=list[AffiliationPublic]
)
async def list_user_affiliations(user_id: UUID, session: Session, _: ReadUser):
    if await session.get(User, user_id) is None:
        raise not_found('User not found')
    items = list(
        await session.scalars(
            select(UserInstitutionalAffiliation)
            .where(UserInstitutionalAffiliation.user_id == user_id)
            .order_by(
                UserInstitutionalAffiliation.created_at.desc(),
                UserInstitutionalAffiliation.id.desc(),
            )
        )
    )
    return [await affiliation_public(session, item) for item in items]


@router.post(
    '/users/{user_id}/affiliations',
    response_model=AffiliationPublic,
    status_code=HTTPStatus.CREATED,
)
async def create_affiliation(
    user_id: UUID,
    payload: AffiliationCreate,
    session: Session,
    actor: AffiliationManager,
    _: TrustedOrigin,
):
    user = await session.get(User, user_id)
    if user is None:
        raise not_found('User not found')
    if user.deleted_at is not None:
        raise conflict('User is inactive')
    institution = await get_institution(session, payload.institution_id)
    if institution.deleted_at is not None:
        raise conflict('Institution is inactive')
    laboratory = None
    if payload.laboratory_id is not None:
        laboratory = await get_laboratory(session, payload.laboratory_id)
        if laboratory.deleted_at is not None:
            raise conflict('Laboratory is inactive')
        if laboratory.institution_id != institution.id:
            raise conflict('Laboratory does not belong to institution')
    item = UserInstitutionalAffiliation(
        user_id=user.id,
        institution_id=institution.id,
        laboratory_id=payload.laboratory_id,
    )
    item.set_creation_audit(actor.id)
    session.add(item)
    await flush_or_conflict(session, 'Active affiliation already exists')
    record_change(
        session, 'affiliation.created', 'affiliation', item.id, actor.id
    )
    await commit_or_conflict(session, 'Active affiliation already exists')
    await session.refresh(item)
    return await affiliation_public(session, item)


@router.delete(
    '/users/{user_id}/affiliations/{affiliation_id}',
    status_code=HTTPStatus.NO_CONTENT,
)
async def deactivate_affiliation(
    user_id: UUID,
    affiliation_id: UUID,
    session: Session,
    actor: AffiliationManager,
    _: TrustedOrigin,
) -> Response:
    item = await session.scalar(
        select(UserInstitutionalAffiliation).where(
            UserInstitutionalAffiliation.id == affiliation_id,
            UserInstitutionalAffiliation.user_id == user_id,
        )
    )
    if item is None:
        raise not_found('Affiliation not found')
    if item.deleted_at is not None:
        raise conflict('Affiliation is inactive')
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'affiliation.deactivated', 'affiliation', item.id, actor.id
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/me/affiliations', response_model=list[SelfAffiliationPublic])
async def list_my_affiliations(session: Session, user: CurrentUser):
    items = await active_institutional_affiliations(session, user.id)
    response = []
    for item in items:
        public = await affiliation_public(session, item)
        response.append(
            SelfAffiliationPublic(
                id=public.id,
                institution=public.institution,
                laboratory=public.laboratory,
            )
        )
    return response


@router.get('/changes', response_model=InstitutionalChangePage)
async def list_changes(
    session: Session,
    _: ReadUser,
    offset: int = 0,
    limit: int = MAX_HISTORY_LIMIT,
):
    if offset < 0 or limit < 1 or limit > MAX_HISTORY_LIMIT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Invalid pagination',
        )
    items = list(
        await session.scalars(
            select(InstitutionalChange)
            .order_by(
                InstitutionalChange.created_at.desc(),
                InstitutionalChange.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return InstitutionalChangePage(
        offset=offset,
        limit=limit,
        items=[
            InstitutionalChangePublic(
                id=item.id,
                action=item.action,
                target_type=item.target_type,
                target_id=item.target_id,
                actor_user_id=item.created_by,
                occurred_at=item.created_at,
            )
            for item in items
        ],
    )

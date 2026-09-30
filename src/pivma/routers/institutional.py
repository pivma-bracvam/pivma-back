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
from pivma.core.errors import api_error
from pivma.core.listing import (
    PageQuery,
    PerPageQuery,
    build_pagination,
    paginate_items,
    paginate_query,
)
from pivma.core.participant_service import (
    record_laboratory_validity_changes,
    snapshot_laboratory_designations,
)
from pivma.core.references import institution_ref, laboratory_ref, user_refs
from pivma.dependencies import (
    CurrentUser,
    Session,
    TrustedOrigin,
    require_permission,
)
from pivma.schemas import (
    AffiliationCreate,
    AffiliationListResponse,
    AffiliationPublic,
    InstitutionalChangeListResponse,
    InstitutionalChangePublic,
    InstitutionCreate,
    InstitutionListResponse,
    InstitutionPublic,
    InstitutionUpdate,
    LaboratoryCreate,
    LaboratoryListResponse,
    LaboratoryPublic,
    LaboratoryUpdate,
    NoFilters,
    SelfAffiliationListResponse,
    SelfAffiliationPublic,
    SortApplied,
)

router = APIRouter(prefix='/institutional', tags=['institutional'])
ReadUser = Annotated[User, Depends(require_permission(INSTITUTIONAL_READ))]
CatalogManager = Annotated[
    User, Depends(require_permission(INSTITUTIONAL_CATALOGS_MANAGE))
]
AffiliationManager = Annotated[
    User, Depends(require_permission(INSTITUTIONAL_AFFILIATIONS_MANAGE))
]


def not_found(detail: str) -> HTTPException:
    return api_error(HTTPStatus.NOT_FOUND, 'not_found', detail)


def conflict(detail: str, code: str = 'conflict') -> HTTPException:
    return api_error(HTTPStatus.CONFLICT, code, detail)


def inactive(detail: str) -> HTTPException:
    return conflict(detail, 'inactive_entity')


async def commit_or_conflict(session: Session, detail: str) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise conflict(detail, 'duplicate') from None


async def flush_or_conflict(session: Session, detail: str) -> None:
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise conflict(detail, 'duplicate') from None


def institution_public(item: Institution) -> InstitutionPublic:
    return InstitutionPublic(
        **institution_ref(item).model_dump(),
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


def laboratory_public(
    item: Laboratory, institution: Institution
) -> LaboratoryPublic:
    return LaboratoryPublic(
        id=item.id,
        name=item.name,
        active=item.deleted_at is None,
        institution=institution_ref(institution),
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


def _laboratory_ids(laboratory_id: UUID | None) -> list[UUID]:
    return [] if laboratory_id is None else [laboratory_id]


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
    # Inativas continuam consultáveis por id (o campo `active` é quem
    # informa o estado); só listagens padrão as ocultam (Spec 022).
    item = await session.get(
        Institution,
        institution_id,
        execution_options={'skip_soft_delete_filter': True},
    )
    if item is None:
        raise not_found('Instituição não encontrada.')
    return item


async def get_laboratory(session: Session, laboratory_id: UUID) -> Laboratory:
    item = await session.get(
        Laboratory,
        laboratory_id,
        execution_options={'skip_soft_delete_filter': True},
    )
    if item is None:
        raise not_found('Laboratório não encontrado.')
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
    laboratory_institution = (
        institution
        if laboratory is None or laboratory.institution_id == institution.id
        else await get_institution(session, laboratory.institution_id)
    )
    return AffiliationPublic(
        id=item.id,
        user=(await user_refs(session, [item.user_id]))[item.user_id],
        institution=institution_ref(institution),
        laboratory=(
            laboratory_ref(laboratory, laboratory_institution)
            if laboratory
            else None
        ),
        active=active,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
        deleted_by=item.deleted_by,
        deleted_at=item.deleted_at,
    )


@router.get('/institutions', response_model=InstitutionListResponse)
async def list_institutions(
    session: Session,
    _: ReadUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    items, total = await paginate_query(
        session,
        select(Institution),
        order_by=(func.lower(Institution.name), Institution.id),
        page=page,
        per_page=per_page,
    )
    return InstitutionListResponse(
        data=[institution_public(item) for item in items],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='name', order='asc'),
    )


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
    await flush_or_conflict(
        session, 'Já existe uma instituição com este nome.'
    )
    record_change(
        session, 'institution.created', 'institution', item.id, actor.id
    )
    await commit_or_conflict(
        session, 'Já existe uma instituição com este nome.'
    )
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
        raise inactive('Instituição inativa.')
    item.name = payload.name
    item.set_update_audit(actor.id)
    await flush_or_conflict(
        session, 'Já existe uma instituição com este nome.'
    )
    record_change(
        session, 'institution.updated', 'institution', item.id, actor.id
    )
    await commit_or_conflict(
        session, 'Já existe uma instituição com este nome.'
    )
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
        raise inactive('Instituição inativa.')
    snapshot = await snapshot_laboratory_designations(
        session,
        laboratory_ids=await session.scalars(
            select(Laboratory.id).where(Laboratory.institution_id == item.id)
        ),
    )
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'institution.deactivated', 'institution', item.id, actor.id
    )
    await record_laboratory_validity_changes(
        session, snapshot, actor_id=actor.id, reason='institution_deactivated'
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/laboratories', response_model=LaboratoryListResponse)
async def list_laboratories(
    session: Session,
    _: ReadUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    items, total = await paginate_query(
        session,
        select(Laboratory),
        order_by=(
            Laboratory.institution_id,
            func.lower(Laboratory.name),
            Laboratory.id,
        ),
        page=page,
        per_page=per_page,
    )
    institutions = {
        institution.id: institution
        for institution in await session.scalars(
            select(Institution)
            .where(Institution.id.in_({i.institution_id for i in items}))
            .execution_options(skip_soft_delete_filter=True)
        )
    }
    return LaboratoryListResponse(
        data=[
            laboratory_public(item, institutions[item.institution_id])
            for item in items
        ],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='institution', order='asc'),
    )


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
        raise inactive('Instituição inativa.')
    item = Laboratory(institution_id=institution.id, name=payload.name)
    item.set_creation_audit(actor.id)
    session.add(item)
    await flush_or_conflict(session, 'Já existe um laboratório com este nome.')
    record_change(
        session, 'laboratory.created', 'laboratory', item.id, actor.id
    )
    await commit_or_conflict(
        session, 'Já existe um laboratório com este nome.'
    )
    await session.refresh(item)
    return laboratory_public(
        item, await get_institution(session, item.institution_id)
    )


@router.get('/laboratories/{laboratory_id}', response_model=LaboratoryPublic)
async def read_laboratory(laboratory_id: UUID, session: Session, _: ReadUser):
    item = await get_laboratory(session, laboratory_id)
    return laboratory_public(
        item, await get_institution(session, item.institution_id)
    )


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
        raise inactive('Laboratório inativo.')
    item.name = payload.name
    item.set_update_audit(actor.id)
    await flush_or_conflict(session, 'Já existe um laboratório com este nome.')
    record_change(
        session, 'laboratory.updated', 'laboratory', item.id, actor.id
    )
    await commit_or_conflict(
        session, 'Já existe um laboratório com este nome.'
    )
    await session.refresh(item)
    return laboratory_public(
        item, await get_institution(session, item.institution_id)
    )


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
        raise inactive('Laboratório inativo.')
    snapshot = await snapshot_laboratory_designations(
        session, laboratory_ids=[item.id]
    )
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'laboratory.deactivated', 'laboratory', item.id, actor.id
    )
    await record_laboratory_validity_changes(
        session, snapshot, actor_id=actor.id, reason='laboratory_deactivated'
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get(
    '/users/{user_id}/affiliations', response_model=AffiliationListResponse
)
async def list_user_affiliations(
    user_id: UUID,
    session: Session,
    _: ReadUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    if await session.get(User, user_id) is None:
        raise not_found('Usuário não encontrado.')
    items, total = await paginate_query(
        session,
        select(UserInstitutionalAffiliation).where(
            UserInstitutionalAffiliation.user_id == user_id
        ),
        order_by=(
            UserInstitutionalAffiliation.created_at.desc(),
            UserInstitutionalAffiliation.id.desc(),
        ),
        page=page,
        per_page=per_page,
    )
    return AffiliationListResponse(
        data=[await affiliation_public(session, item) for item in items],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='created_at', order='desc'),
    )


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
        raise not_found('Usuário não encontrado.')
    if user.deleted_at is not None:
        raise inactive('Usuário inativo.')
    institution = await get_institution(session, payload.institution_id)
    if institution.deleted_at is not None:
        raise inactive('Instituição inativa.')
    laboratory = None
    if payload.laboratory_id is not None:
        laboratory = await get_laboratory(session, payload.laboratory_id)
        if laboratory.deleted_at is not None:
            raise inactive('Laboratório inativo.')
        if laboratory.institution_id != institution.id:
            raise conflict(
                'O laboratório não pertence à instituição informada.'
            )
    snapshot = await snapshot_laboratory_designations(
        session,
        laboratory_ids=_laboratory_ids(payload.laboratory_id),
        user_id=user.id,
    )
    item = UserInstitutionalAffiliation(
        user_id=user.id,
        institution_id=institution.id,
        laboratory_id=payload.laboratory_id,
    )
    item.set_creation_audit(actor.id)
    session.add(item)
    await flush_or_conflict(session, 'O usuário já tem esta afiliação ativa.')
    record_change(
        session, 'affiliation.created', 'affiliation', item.id, actor.id
    )
    await record_laboratory_validity_changes(
        session, snapshot, actor_id=actor.id, reason='affiliation_created'
    )
    await commit_or_conflict(session, 'O usuário já tem esta afiliação ativa.')
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
        raise not_found('Afiliação não encontrada.')
    if item.deleted_at is not None:
        raise inactive('Afiliação inativa.')
    snapshot = await snapshot_laboratory_designations(
        session,
        laboratory_ids=_laboratory_ids(item.laboratory_id),
        user_id=user_id,
    )
    item.set_deletion_audit(actor.id)
    record_change(
        session, 'affiliation.deactivated', 'affiliation', item.id, actor.id
    )
    await record_laboratory_validity_changes(
        session, snapshot, actor_id=actor.id, reason='affiliation_ended'
    )
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/me/affiliations', response_model=SelfAffiliationListResponse)
async def list_my_affiliations(
    session: Session,
    user: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    # O serviço já filtra e ordena (created_at desc, id desc); a paginação
    # vem depois do filtro (Spec 033, R2).
    items, total = paginate_items(
        await active_institutional_affiliations(session, user.id),
        page,
        per_page,
    )
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
    return SelfAffiliationListResponse(
        data=response,
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='created_at', order='desc'),
    )


@router.get('/changes', response_model=InstitutionalChangeListResponse)
async def list_changes(
    session: Session,
    _: ReadUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    items, total = await paginate_query(
        session,
        select(InstitutionalChange),
        order_by=(
            InstitutionalChange.created_at.desc(),
            InstitutionalChange.id.desc(),
        ),
        page=page,
        per_page=per_page,
    )
    return InstitutionalChangeListResponse(
        data=[
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
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='occurred_at', order='desc'),
    )

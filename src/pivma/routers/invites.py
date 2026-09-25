"""Rotas públicas de aceite de convite de designação (Spec 028).

Separado de ``process_participants.py`` porque estas duas rotas não vivem sob
``/processes/{process_id}/...`` — quem abre um link de convite não conhece
(nem precisa conhecer) o identificador do processo de antemão. As rotas de
gestão do convite (criar/listar/reenviar/revogar) ficam em
``process_participants.py``, sob o processo, como o restante da Spec 006.
"""

from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from pivma.core.database.models import ProcessInstance
from pivma.core.invite_service import (
    accept_invite,
    get_invite_by_token,
    invite_public_kwargs,
    is_expired,
    mask_email,
)
from pivma.core.process_engine import ConflictError, NotFoundError
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.schemas import InviteAcceptResponse, InvitePreview, InvitePublic

router = APIRouter(prefix='/invites', tags=['Role Assignment Invites'])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail='Convite não encontrado.'
    )


@router.get(
    '/{token}', response_model=InvitePreview, status_code=HTTPStatus.OK
)
async def preview_invite(token: str, session: Session):
    invite = await get_invite_by_token(session, token)
    if invite is None or invite.status != 'pending':
        raise _not_found()

    process = await session.get(ProcessInstance, invite.process_instance_id)
    if process is None:
        raise _not_found()

    return InvitePreview(
        role_key=invite.role_key,
        process_code=process.code,
        process_title=process.title,
        masked_email=mask_email(invite.email),
        expires_at=invite.expires_at,
        expired=is_expired(invite),
    )


@router.post(
    '/{token}/accept',
    response_model=InviteAcceptResponse,
    status_code=HTTPStatus.OK,
)
async def accept_invite_endpoint(
    token: str,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    invite = await get_invite_by_token(session, token)
    if invite is None:
        raise _not_found()

    # FR-010: e-mail da sessão autenticada precisa bater com o do convite —
    # verificado aqui (não em invite_service.accept_invite) porque é 403,
    # não 409, e current_user já está disponível neste nível.
    if current_user.email.lower() != invite.email.lower():
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='O e-mail autenticado não corresponde ao convite.',
        )

    try:
        invite, assignment_id = await accept_invite(
            session, invite, current_user
        )
    except NotFoundError as e:
        raise _not_found() from e
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e

    await session.commit()
    await session.refresh(invite)

    return InviteAcceptResponse(
        invite=InvitePublic(**invite_public_kwargs(invite)),
        assignment_id=assignment_id,
        process_id=invite.process_instance_id,
        role_key=invite.role_key,
    )

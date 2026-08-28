from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database import get_session
from pivma.core.database.models import User
from pivma.core.security import hash_password
from pivma.schemas import (
    UserPublic,
    UserSchema,
)

router = APIRouter(prefix='/users', tags=['users'])
Session = Annotated[AsyncSession, Depends(get_session)]


async def find_conflict(session: AsyncSession, user: UserSchema):
    username_exists = await session.scalar(
        select(User.id).where(
            func.lower(User.username) == func.lower(user.username),
            User.deleted_at.is_(None),
        )
    )
    if username_exists:
        return 'Username already exists'

    email_exists = await session.scalar(
        select(User.id).where(
            func.lower(User.email) == func.lower(user.email),
            User.deleted_at.is_(None),
        )
    )
    if email_exists:
        return 'Email already exists'
    return None


async def persist_user(
    session: AsyncSession, user: UserSchema, password_hash: str
) -> User:
    db_user = User(
        email=user.email,
        username=user.username,
        password_hash=password_hash,
    )
    session.add(db_user)
    await session.flush()
    await session.refresh(db_user)
    await session.commit()
    return db_user


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    conflict = await find_conflict(session, user)
    if conflict:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=conflict,
        )

    try:
        password_hash = await run_in_threadpool(hash_password, user.password)
        db_user = await persist_user(session, user, password_hash)
    except IntegrityError:
        await session.rollback()
        conflict = await find_conflict(session, user)
        if conflict:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=conflict,
            ) from None
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None

    return db_user

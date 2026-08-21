import pytest
from sqlalchemy.exc import IntegrityError

from tests.factories.process_factory import (
    FormFieldFactory,
    FormTemplateFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)


@pytest.mark.asyncio
async def test_process_template_unique_key(session):
    t1 = ProcessTemplateFactory(key='unique_test')
    session.add(t1)
    await session.commit()

    t2 = ProcessTemplateFactory(key='unique_test')
    session.add(t2)
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_process_template_version_unique_version_number(session):
    t = ProcessTemplateFactory()
    session.add(t)
    await session.commit()

    v1 = ProcessTemplateVersionFactory(template=t, version_number=1)
    session.add(v1)
    await session.commit()

    v2 = ProcessTemplateVersionFactory(template=t, version_number=1)
    session.add(v2)
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_form_field_unique_key_per_template(session):
    ft = FormTemplateFactory()
    session.add(ft)
    await session.commit()

    f1 = FormFieldFactory(form_template=ft, field_key='email_field')
    session.add(f1)
    await session.commit()

    f2 = FormFieldFactory(form_template=ft, field_key='email_field')
    session.add(f2)
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

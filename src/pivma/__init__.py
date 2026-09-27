import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from pivma.core.logging import setup_logging
from pivma.core.pre_evaluation_service import sweep_stale_runs
from pivma.core.settings import Settings
from pivma.errors import install_openapi, register_error_handlers
from pivma.routers import (
    admin_logs,
    ai_evaluations,
    auth,
    forms,
    institutional,
    invites,
    pre_evaluation,
    process_participants,
    processes,
    rbac,
    return_review,
    samples,
    tasks,
    triage,
    users,
)

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await sweep_stale_runs()
    except Exception:  # noqa: BLE001 - startup nunca deve quebrar por isso
        logger.exception('startup.sweep_stale_runs failed')
    yield


app = FastAPI(
    swagger_ui_parameters={'withCredentials': True},
    lifespan=lifespan,
)
settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.AUTH_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Content-Type'],
)


register_error_handlers(app)
install_openapi(app)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(rbac.router)
app.include_router(institutional.router)
app.include_router(processes.router)
app.include_router(process_participants.router)
app.include_router(invites.router)
app.include_router(forms.router)
app.include_router(admin_logs.router)
app.include_router(triage.router)
app.include_router(tasks.router)
app.include_router(ai_evaluations.router)
app.include_router(ai_evaluations.templates_router)
app.include_router(pre_evaluation.router)
app.include_router(pre_evaluation.admin_router)
app.include_router(return_review.router)
app.include_router(samples.router)


@app.get('/')
def read_root():
    return {'message': 'Hello World!'}

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from pivma.core.logging import setup_logging
from pivma.core.pre_evaluation_service import sweep_stale_runs
from pivma.core.settings import Settings
from pivma.routers import (
    admin_logs,
    ai_evaluations,
    auth,
    forms,
    institutional,
    pre_evaluation,
    process_participants,
    processes,
    rbac,
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


@app.exception_handler(RequestValidationError)
async def sanitize_password_validation_error(request, exc):
    if any('password' in error.get('loc', ()) for error in exc.errors()):
        return JSONResponse(
            status_code=422,
            content={'detail': 'Invalid password'},
        )
    return await request_validation_exception_handler(request, exc)


app.include_router(users.router)
app.include_router(auth.router)
app.include_router(rbac.router)
app.include_router(institutional.router)
app.include_router(processes.router)
app.include_router(process_participants.router)
app.include_router(forms.router)
app.include_router(forms.direct_forms_router)
app.include_router(admin_logs.router)
app.include_router(triage.router)
app.include_router(tasks.router)
app.include_router(ai_evaluations.router)
app.include_router(ai_evaluations.templates_router)
app.include_router(pre_evaluation.router)
app.include_router(pre_evaluation.admin_router)


@app.get('/')
def read_root():
    return {'message': 'Hello World!'}


demos_dir = Path(__file__).resolve().parents[2] / 'demos'
demos_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    '/demos',
    StaticFiles(directory=str(demos_dir), html=True),
    name='demos',
)

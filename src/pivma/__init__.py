from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from pivma.core.settings import Settings
from pivma.routers import auth, rbac, users

app = FastAPI()
settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.AUTH_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
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


@app.get('/')
def read_root():
    return {'message': 'Hello World!'}

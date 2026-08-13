from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pivma.routers import users

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def sanitize_password_validation_error(request, exc):
    if any('password' in error.get('loc', ()) for error in exc.errors()):
        return JSONResponse(
            status_code=422,
            content={'detail': 'Invalid password'},
        )
    return await request_validation_exception_handler(request, exc)


app.include_router(users.router)


@app.get('/')
def read_root():
    return {'message': 'Hello World!'}

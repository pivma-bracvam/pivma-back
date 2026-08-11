from fastapi import FastAPI

from pivma.routers import users

app = FastAPI()

app.include_router(users.router)


@app.get('/')
def read_root():
    return {'message': 'Hello World!'}

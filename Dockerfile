FROM python:3.14-slim
WORKDIR app/
COPY . .

RUN pip install .

EXPOSE 8000
CMD uvicorn pivma:app --host 0.0.0.0
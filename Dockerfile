FROM python:3.14-slim
WORKDIR /app
COPY . .

ENV DEMOS_DIR=/app/demos

RUN chmod +x entrypoint.sh && pip install .

EXPOSE 8000
CMD ["uvicorn", "pivma:app", "--host", "0.0.0.0", "--port", "8000"]


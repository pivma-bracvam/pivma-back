from fastapi.testclient import TestClient

from pivma import app

client = TestClient(app)

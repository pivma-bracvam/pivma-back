from http import HTTPStatus

from fastapi.testclient import TestClient

from pivma import app


def test_root_should_return_ok_and_hello_world():
    client = TestClient(app)

    response = client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Hello World!'}


def test_prototypes_endpoint_should_return_html():
    client = TestClient(app)

    response = client.get('/prototypes/')

    assert response.status_code == HTTPStatus.OK
    assert 'PIVMA' in response.text


def test_forms_and_triage_prototype_endpoint_should_return_html():
    client = TestClient(app)

    response = client.get('/prototypes/forms-and-triage/')

    assert response.status_code == HTTPStatus.OK
    assert 'Modelagem e Customização do Formulário' in response.text


from http import HTTPStatus

from fastapi.testclient import TestClient

from pivma import app


def test_root_should_return_ok_and_hello_world():
    client = TestClient(app)

    response = client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Hello World!'}


def test_demos_004_catalog_endpoint_should_return_html():
    client = TestClient(app)

    # Testando tanto com barra quanto sem barra
    for path in ['/demos/004', '/demos/004/']:
        response = client.get(path, follow_redirects=True)
        assert response.status_code == HTTPStatus.OK
        assert 'Spec 004: Submissão e Triagem' in response.text
        assert '1. Modelagem do Formulário' in response.text
        assert '2. Preenchimento e Submissão' in response.text
        assert '3. Avaliação e Triagem Técnica' in response.text


def test_demos_004_individual_pages_should_return_html():
    client = TestClient(app)

    pages = [
        ('modelagem.html', '1. Modelagem do Formulário (Form Builder)'),
        ('preenchimento.html', '2. Preenchimento e Submissão da Proposta'),
        ('triagem.html', '3. Avaliação e Triagem Técnica do Método'),
    ]

    for filename, expected_title in pages:
        response = client.get(f'/demos/004/{filename}')
        assert response.status_code == HTTPStatus.OK
        assert expected_title in response.text

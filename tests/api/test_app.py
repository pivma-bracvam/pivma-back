from http import HTTPStatus

from fastapi.testclient import TestClient

from pivma import app, resolve_demos_dir


def test_root_should_return_ok_and_hello_world():
    client = TestClient(app)

    response = client.get('/')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Hello World!'}


def test_demos_mount_should_serve_catalog():
    client = TestClient(app)

    response = client.get('/demos/')
    assert response.status_code == HTTPStatus.OK
    assert 'PIVMA — Hub de Demonstrações' in response.text

    response_no_slash = client.get('/demos')
    assert response_no_slash.status_code == HTTPStatus.OK

    css_response = client.get('/demos/assets/base.css')
    assert css_response.status_code == HTTPStatus.OK


def test_resolve_demos_dir_explicit_and_fallback(tmp_path, monkeypatch):
    custom_dir = tmp_path / 'custom_demos'
    custom_dir.mkdir()

    resolved = resolve_demos_dir(str(custom_dir))
    assert resolved == custom_dir.resolve()

    monkeypatch.setattr('pathlib.Path.is_dir', lambda self: False)
    assert resolve_demos_dir('non_existent') is None

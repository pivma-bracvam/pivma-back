"""PubChem simulado para a consulta por CAS (Spec 040, US2).

Respostas no formato real (conferido em 2026-10-04): formaldeído, CID 712.
O primeiro bloco "Pictogram(s)" é o que vale; o segundo existe para provar
que os demais são ignorados.
"""

import httpx
import pytest

from pivma import app
from pivma.routers.samples import pubchem_transport

CID = 712


def _pictogram_block(codes):
    return {
        'Name': 'Pictogram(s)',
        'Value': {
            'StringWithMarkup': [
                {
                    'String': '  ',
                    'Markup': [
                        {
                            'URL': 'https://pubchem.ncbi.nlm.nih.gov/'
                            f'images/ghs/{code}.svg',
                            'Type': 'Icon',
                        }
                        for code in codes
                    ],
                }
            ]
        },
    }


GHS_RECORD = {
    'Record': {
        'RecordNumber': CID,
        'Section': [
            {
                'TOCHeading': 'Safety and Hazards',
                'Section': [
                    {
                        'TOCHeading': 'GHS Classification',
                        'Information': [
                            {'Name': 'Signal', 'Value': {}},
                            _pictogram_block(['GHS05', 'GHS06', 'GHS08']),
                            _pictogram_block(['GHS02', 'GHS07']),
                        ],
                    }
                ],
            }
        ],
    }
}


def pubchem_handler(*, known=True, ghs=True, fail=None):
    """Responde como o PubChem; `fail` força status, JSON ruim ou timeout."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        calls.append(request.url)
        if fail == 'timeout':
            raise httpx.ReadTimeout('lento', request=request)
        if fail == 'status':
            return httpx.Response(500)
        if fail == 'json':
            return httpx.Response(200, json={'inesperado': True})
        path = request.url.path
        if '/cids/' in path:
            if not known:
                return httpx.Response(404, json={'Fault': {}})
            return httpx.Response(200, json={'IdentifierList': {'CID': [CID]}})
        if '/property/' in path:
            return httpx.Response(
                200,
                json={
                    'PropertyTable': {
                        'Properties': [
                            {
                                'CID': CID,
                                'Title': 'Formaldehyde',
                                'IUPACName': 'formaldehyde',
                            }
                        ]
                    }
                },
            )
        if '/pug_view/' in path:
            assert request.url.params['heading'] == 'GHS Classification'
            if not ghs:
                return httpx.Response(404, json={'Fault': {}})
            return httpx.Response(200, json=GHS_RECORD)
        return httpx.Response(404)

    handler.calls = calls
    return handler


@pytest.fixture
def fake_pubchem():
    """Troca o transporte do PubChem; devolve a função que o configura."""

    def _use(**kwargs):
        handler = pubchem_handler(**kwargs)
        transport = httpx.MockTransport(handler)
        app.dependency_overrides[pubchem_transport] = lambda: transport
        return handler

    yield _use
    app.dependency_overrides.pop(pubchem_transport, None)

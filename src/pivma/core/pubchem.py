"""Sugestões de dados de substância pelo CAS no PubChem (Spec 040, US2).

Só consulta e devolve sugestões; nada é gravado (FR-014, FR-016). Formato
das respostas conferido contra o serviço real em 2026-10-04 (research R8).
"""

import re
from typing import Any

import httpx

from pivma.core.settings import Settings

PICTOGRAM_PATTERN = re.compile(r'GHS0[1-9]')
COMPOUND_PAGE = 'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}'


class CompoundNotFoundError(Exception):
    """O PubChem não conhece o CAS."""


class LookupUnavailableError(Exception):
    """Fonte fora do ar, com erro, lenta demais ou em formato inesperado."""


def _sections(node: dict[str, Any]):
    yield node
    for child in node.get('Section', []):
        yield from _sections(child)


def ghs_pictograms(record: dict[str, Any]) -> list[str]:
    """Códigos GHS do primeiro bloco "Pictogram(s)" da classificação.

    É o bloco que o PubChem exibe; os demais repetem notificações de outros
    fornecedores e superestimam o perigo (research R8).
    """
    for section in _sections(record.get('Record', {})):
        for info in section.get('Information', []):
            if info.get('Name') == 'Pictogram(s)':
                urls = ' '.join(
                    markup.get('URL', '')
                    for item in info.get('Value', {}).get(
                        'StringWithMarkup', []
                    )
                    for markup in item.get('Markup', [])
                )
                return list(dict.fromkeys(PICTOGRAM_PATTERN.findall(urls)))
    return []


async def _json(client: httpx.AsyncClient, path: str, **params: str) -> Any:
    """Corpo JSON da resposta; `None` quando o PubChem responde 404."""
    try:
        response = await client.get(path, params=params or None)
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LookupUnavailableError(str(exc)) from exc


async def lookup_by_cas(
    cas: str,
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """CID, nome, nome IUPAC e pictogramas GHS sugeridos para o CAS."""
    async with httpx.AsyncClient(
        base_url=settings.PUBCHEM_BASE_URL,
        timeout=settings.PUBCHEM_TIMEOUT_SECONDS,
        transport=transport,
    ) as client:
        cids = await _json(client, f'/rest/pug/compound/name/{cas}/cids/JSON')
        if cids is None:
            raise CompoundNotFoundError(cas)
        try:
            cid = int(cids['IdentifierList']['CID'][0])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LookupUnavailableError(str(exc)) from exc
        table = await _json(
            client,
            f'/rest/pug/compound/cid/{cid}/property/Title,IUPACName/JSON',
        )
        try:
            properties = table['PropertyTable']['Properties'][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise LookupUnavailableError(str(exc)) from exc
        ghs = await _json(
            client,
            f'/rest/pug_view/data/compound/{cid}/JSON',
            heading='GHS Classification',
        )
    return {
        'cas_number': cas,
        'source': 'pubchem',
        'pubchem_cid': cid,
        'source_url': COMPOUND_PAGE.format(cid=cid),
        'chemical_name': properties.get('Title'),
        'iupac_name': properties.get('IUPACName'),
        'ghs_hazard_pictograms': (
            ghs_pictograms(ghs) if isinstance(ghs, dict) else []
        ),
    }

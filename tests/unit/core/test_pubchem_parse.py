"""Extração dos pictogramas GHS do registro do PubChem (Spec 040, R8)."""

from pivma.core.pubchem import ghs_pictograms
from tests.factories.pubchem_factory import GHS_RECORD


def test_only_first_pictogram_block_counts():
    assert ghs_pictograms(GHS_RECORD) == ['GHS05', 'GHS06', 'GHS08']


def test_record_without_pictograms_gives_empty_list():
    assert ghs_pictograms({'Record': {'Section': []}}) == []

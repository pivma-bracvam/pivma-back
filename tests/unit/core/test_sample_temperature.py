"""Regra de regime e faixa térmica da substância (Spec 040, FR-004/FR-005)."""

import pytest

from pivma.core.sample_service import (
    SampleValidationError,
    resolve_temperature_range,
)


@pytest.mark.parametrize(
    ('regime', 'expected'),
    [
        ('ambient', ('ambient', 15.0, 25.0)),
        ('refrigerated', ('refrigerated', 2.0, 8.0)),
    ],
)
def test_preset_regime_without_range_gets_default(regime, expected):
    assert resolve_temperature_range(regime, None, None) == expected


def test_explicit_range_overrides_preset():
    assert resolve_temperature_range('refrigerated', 0, 4) == (
        'refrigerated',
        0,
        4,
    )


def test_no_regime_and_no_range_is_empty():
    assert resolve_temperature_range(None, None, None) == (None, None, None)


def test_equal_limits_are_accepted():
    assert resolve_temperature_range('custom', 5, 5) == ('custom', 5, 5)


@pytest.mark.parametrize(
    ('regime', 'minimum', 'maximum', 'field'),
    [
        (None, 2, None, 'storage_temperature_regime'),
        (None, None, 8, 'storage_temperature_regime'),
        ('frozen', None, None, 'storage_temperature_min'),
        ('deep_frozen', -90, None, 'storage_temperature_max'),
        ('custom', None, 30, 'storage_temperature_min'),
        ('refrigerated', 2, None, 'storage_temperature_max'),
        ('custom', 9, 8, 'storage_temperature_min'),
    ],
)
def test_incoherent_range_is_refused(regime, minimum, maximum, field):
    with pytest.raises(SampleValidationError) as error:
        resolve_temperature_range(regime, minimum, maximum)

    assert error.value.code == 'invalid_temperature_range'
    assert error.value.extra['fields'][0]['field'] == field


# Spec 040, Jornada 4: tipo de desvio no alerta do Grupo de Seleção.


@pytest.mark.parametrize(
    ('deviations', 'kind'),
    [
        (['temperature_out_of_range'], 'térmico'),
        (['package_damaged'], 'físico'),
        (['package_violated'], 'físico'),
        (['temperature_out_of_range', 'package_violated'], 'térmico e físico'),
    ],
)
def test_alert_names_the_deviation_kind(deviations, kind):
    from pivma.core.sample_receipt_service import (  # noqa: PLC0415
        deviation_kind,
    )

    assert deviation_kind(deviations) == kind

import pytest
from pint import DimensionalityError
from mrp.units import (
    parse_mass, parse_volume, parse_molar_mass, parse_volume_ratio,
    parse_quantity_from_yaml, to_float, ureg,
)


def test_parse_mass_rejects_volume_unit():
    with pytest.raises(ValueError, match="not a recognised mass unit"):
        parse_mass(1.0, "L")

def test_parse_volume_rejects_mass_unit():
    with pytest.raises(ValueError, match="not a recognised volume unit"):
        parse_volume(1.0, "kg")

def test_parse_quantity_from_yaml_unknown_unit():
    with pytest.raises(ValueError, match="Unrecognised unit"):
        parse_quantity_from_yaml(1.0, "furlongs")

def test_parse_mass_valid():
    q = parse_mass(1000.0, "g")
    assert abs(to_float(q, "kg") - 1.0) < 1e-9

def test_parse_volume_valid():
    q = parse_volume(1000.0, "mL")
    assert abs(to_float(q, "L") - 1.0) < 1e-9

def test_pint_mass_div_mw_gives_mol():
    mass = ureg.Quantity(110.13, "kg")
    mw   = ureg.Quantity(110.13, "g/mol")
    moles = (mass / mw).to("mol")
    assert abs(moles.magnitude - 1000.0) < 0.01

def test_pint_mol_times_mw_gives_kg():
    moles = ureg.Quantity(1000.0, "mol")
    mw    = ureg.Quantity(110.13, "g/mol")
    mass  = (moles * mw).to("kg")
    assert abs(mass.magnitude - 110.13) < 0.01

def test_pint_kg_times_volume_ratio_gives_L():
    mass  = ureg.Quantity(100.0, "kg")
    ratio = ureg.Quantity(10.0, "L/kg")
    vol   = (mass * ratio).to("L")
    assert abs(vol.magnitude - 1000.0) < 1e-9
    assert str(vol.units) == "liter"

def test_pint_add_L_to_kg_raises_dimensionality_error():
    with pytest.raises(DimensionalityError):
        _ = ureg.Quantity(1.0, "L") + ureg.Quantity(1.0, "kg")

def test_parse_volume_ratio_units():
    q = parse_volume_ratio(10.0)
    assert "liter" in str(q.units) or "L" in str(q.units)
    # Check dimension is length^3/mass (L/kg)
    converted = (ureg.Quantity(100.0, "kg") * q).to("L")
    assert abs(converted.magnitude - 1000.0) < 1e-9

def test_to_float_unit_conversion():
    q = ureg.Quantity(1000.0, "g")
    assert abs(to_float(q, "kg") - 1.0) < 1e-9

def test_parse_quantity_from_yaml_dispatches_mass():
    q = parse_quantity_from_yaml(5.0, "kg")
    assert abs(to_float(q, "kg") - 5.0) < 1e-9

def test_parse_quantity_from_yaml_dispatches_volume():
    q = parse_quantity_from_yaml(10.0, "L")
    assert abs(to_float(q, "L") - 10.0) < 1e-9

def test_parse_molar_mass():
    q = parse_molar_mass(180.16)
    assert abs(q.magnitude - 180.16) < 1e-9
